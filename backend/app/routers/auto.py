from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import DockingJob, User
from app.schemas import BoxParams, DockingJobOut
from app.services.converter import sdf_to_pdbqt, pdb_to_pdbqt
from app.services.docking import execute_docking_job
from app.services.grid import predict_grid_from_pdb
from app.services.subscriptions import ensure_can_start_job
from app.routers.docking import serialize_job


router = APIRouter(prefix="/auto", tags=["Auto Workflow"])


@router.get("/test")
def auto_test():
    return {
        "message": "Auto workflow route is working"
    }


@router.post("/prepare")
def auto_prepare(
    protein: str,
    compound: str,
    user: User = Depends(get_current_user),
):
    return _prepare_auto_inputs(protein=protein, compound=compound)


def _prepare_auto_inputs(protein: str, compound: str):
    try:
        settings = get_settings()
        settings.storage_dir.mkdir(parents=True, exist_ok=True)

        cid_url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            f"{compound}/cids/JSON"
        )

        cid_response = requests.get(cid_url, timeout=20)
        cid_response.raise_for_status()

        cid = cid_response.json()["IdentifierList"]["CID"][0]

        sdf_url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
            f"{cid}/SDF?record_type=3d"
        )

        sdf_response = requests.get(sdf_url, timeout=30)

        if sdf_response.status_code != 200:
            raise HTTPException(status_code=404, detail="3D SDF not available")

        sdf_path = settings.storage_dir / f"compound_{cid}.sdf"

        with open(sdf_path, "w", encoding="utf-8") as f:
            f.write(sdf_response.text)

        ligand_pdbqt = sdf_to_pdbqt(str(sdf_path))

        pdb_query = {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {
                    "value": protein
                },
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {
                    "start": 0,
                    "rows": 1,
                }
            },
        }

        pdb_search = requests.post(
            "https://search.rcsb.org/rcsbsearch/v2/query",
            json=pdb_query,
            timeout=20,
        )

        pdb_search.raise_for_status()

        result_set = pdb_search.json().get("result_set", [])

        if not result_set:
            raise HTTPException(status_code=404, detail="No PDB found for protein")

        pdb_id = result_set[0]["identifier"]

        pdb_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        pdb_response = requests.get(pdb_url, timeout=30)

        if pdb_response.status_code != 200:
            raise HTTPException(status_code=404, detail="PDB download failed")

        pdb_path = settings.storage_dir / f"{pdb_id}.pdb"

        with open(pdb_path, "w", encoding="utf-8") as f:
            f.write(pdb_response.text)

        receptor_pdbqt = pdb_to_pdbqt(str(pdb_path))

        grid = predict_grid_from_pdb(pdb_path)

        return {
            "message": "Auto preparation completed successfully",
            "compound": {
                "query": compound,
                "cid": cid,
                "sdf_path": str(sdf_path),
                "ligand_pdbqt": ligand_pdbqt,
            },
            "protein": {
                "query": protein,
                "pdb_id": pdb_id,
                "pdb_path": str(pdb_path),
                "receptor_pdbqt": receptor_pdbqt,
            },
            "grid": grid,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dock", response_model=DockingJobOut, status_code=status.HTTP_202_ACCEPTED)
def auto_dock(
    protein: str,
    compound: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_can_start_job(db, user)
    prepared = _prepare_auto_inputs(protein=protein, compound=compound)

    settings = get_settings()
    grid = prepared["grid"]

    box = BoxParams(
        center_x=grid["center_x"],
        center_y=grid["center_y"],
        center_z=grid["center_z"],
        size_x=grid["size_x"],
        size_y=grid["size_y"],
        size_z=grid["size_z"],
        exhaustiveness=16,
        num_modes=10,
    )

    job = DockingJob(
        user_id=user.id,
        protein_name=prepared["protein"]["pdb_id"],
        ligand_name=compound,
        work_dir="",
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    work_dir = settings.storage_dir / "jobs" / job.id

    job.work_dir = str(work_dir)
    job.input_json = {
        "protein_path": prepared["protein"]["receptor_pdbqt"],
        "protein_sha256": "",
        "ligand_path": prepared["compound"]["ligand_pdbqt"],
        "ligand_sha256": "",
        "box": box.model_dump(),
        "cpu": settings.max_parallel_cpu,
    }

    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(execute_docking_job, job.id)

    return serialize_job(job)
