from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import DockingJob, User
from app.schemas import BoxParams, DockingJobOut, JobFileLinks
from app.services.docking import execute_docking_job
from app.services.files import (
    ALLOWED_LIGAND_EXTENSIONS,
    ALLOWED_PROTEIN_EXTENSIONS,
    assert_inside_storage,
    persist_upload,
    safe_filename,
)
from app.services.subscriptions import ensure_can_start_job


router = APIRouter(prefix="/dock", tags=["docking"])


@router.post("", response_model=DockingJobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_docking_job(
    background_tasks: BackgroundTasks,
    protein_name: str = Form("Protein"),
    ligand_name: str = Form("Ligand"),
    center_x: float = Form(0),
    center_y: float = Form(0),
    center_z: float = Form(0),
    size_x: float = Form(20),
    size_y: float = Form(20),
    size_z: float = Form(20),
    exhaustiveness: int = Form(16),
    num_modes: int = Form(10),
    ligand_smiles: str = Form(""),
    protein_file: UploadFile | None = File(None),
    ligand_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DockingJobOut:
    ensure_can_start_job(db, user)
    if protein_file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Protein file is required")
    if ligand_file is None and not ligand_smiles.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a ligand file or provide SMILES")

    box = BoxParams(
        center_x=center_x,
        center_y=center_y,
        center_z=center_z,
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        exhaustiveness=exhaustiveness,
        num_modes=num_modes,
    )

    settings = get_settings()
    job = DockingJob(
        user_id=user.id,
        protein_name=protein_name.strip()[:255] or "Protein",
        ligand_name=ligand_name.strip()[:255] or "Ligand",
        work_dir="",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    work_dir = settings.storage_dir / "jobs" / job.id
    inputs_dir = work_dir / "inputs"
    protein = await persist_upload(protein_file, inputs_dir, ALLOWED_PROTEIN_EXTENSIONS)

    ligand_path: Path
    ligand_sha256 = ""
    if ligand_file is not None:
        ligand = await persist_upload(ligand_file, inputs_dir, ALLOWED_LIGAND_EXTENSIONS)
        ligand_path = ligand.path
        ligand_sha256 = ligand.sha256
        ligand_name = ligand.original_name
    else:
        clean_ligand_name = safe_filename(ligand_name or "ligand")
        ligand_path = inputs_dir / f"{clean_ligand_name}.smi"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        ligand_path.write_text(ligand_smiles.strip() + "\n", encoding="utf-8")
        ligand_name = clean_ligand_name

    job.work_dir = str(work_dir)
    job.protein_name = protein.original_name if protein_file.filename else job.protein_name
    job.ligand_name = ligand_name
    job.input_json = {
        "protein_path": str(protein.path),
        "protein_sha256": protein.sha256,
        "ligand_path": str(ligand_path),
        "ligand_sha256": ligand_sha256,
        "box": box.model_dump(),
        "cpu": settings.max_parallel_cpu,
    }
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(execute_docking_job, job.id)
    return serialize_job(job)


@router.get("", response_model=list[DockingJobOut])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[DockingJobOut]:
    rows = db.execute(
        select(DockingJob).where(DockingJob.user_id == user.id).order_by(desc(DockingJob.created_at)).limit(100)
    ).scalars()
    return [serialize_job(job) for job in rows]


@router.get("/{job_id}", response_model=DockingJobOut)
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DockingJobOut:
    job = owned_job(db, user, job_id)
    return serialize_job(job)


@router.get("/{job_id}/files/{kind}")
def get_job_file(
    job_id: str,
    kind: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    job = owned_job(db, user, job_id)
    result = job.result_json or {}
    path_map = {
    "pose": job.pose_path,
    "receptor": result.get("receptor_path", ""),
    "report": job.report_path,
    "log": job.log_path,
    "result-json": result.get("result_json_path", ""),
}
    if kind not in path_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown file type")
    raw_path = path_map[kind] or ""
    if not raw_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File is not available yet")
    path = Path(raw_path)
    resolved = assert_inside_storage(path)
    if not resolved.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File is missing")

    media_type = "text/plain"
    filename = resolved.name
    if kind == "result-json":
        media_type = "application/json"
        filename = f"{job.id}-result.json"
    if kind == "report":
        media_type = "text/markdown"
        filename = f"{job.id}-report.md"
    return FileResponse(resolved, media_type=media_type, filename=filename)


def owned_job(db: Session, user: User, job_id: str) -> DockingJob:
    job = db.get(DockingJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docking job not found")
    return job


def serialize_job(job: DockingJob) -> DockingJobOut:
    result = job.result_json or {}
    files = JobFileLinks()
    if job.pose_path:
        files.pose = f"/dock/{job.id}/files/pose"
    if result.get("receptor_path"):
        files.receptor = f"/dock/{job.id}/files/receptor"
    if job.report_path:
        files.report = f"/dock/{job.id}/files/report"
    if job.log_path:
        files.log = f"/dock/{job.id}/files/log"
    if result.get("result_json_path"):
        files.result_json = f"/dock/{job.id}/files/result-json"

    return DockingJobOut(
        id=job.id,
        protein_name=job.protein_name,
        ligand_name=job.ligand_name,
        status=job.status,
        best_affinity_kcal_mol=result.get("best_affinity_kcal_mol"),
        modes=result.get("modes", []),
        contacts=result.get("contacts", []),
        warnings=result.get("warnings", []),
        error_message=job.error_message or "",
        files=files,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )
