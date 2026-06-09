import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User, VaccineProject
from app.schemas import (
    VaccineAnalysisRequest,
    VaccineConstructRequest,
    VaccineProjectCreate,
)
from app.services.files import assert_inside_storage
from app.services.iedb import (
    IEDBPredictionError,
    predict_bcell_epitopes,
    predict_mhc_binding,
    predict_mhci_processing,
)
from app.services.ncbi import (
    NCBIServiceError,
    fetch_protein_fasta,
    get_blastp_result,
    search_proteins,
    submit_blastp,
)
from app.services.vaccine_design import (
    assemble_construct,
    profile_sequence,
    rank_epitope_candidates,
)
from app.services.vaccine_reports import write_vaccine_artifacts


router = APIRouter(prefix="/vaccine", tags=["vaccine"])

VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
WINDOW_BY_CONSTRUCT = {
    "mhc-i": 9,
    "mhc-ii": 15,
    "b-cell": 12,
    "multi-epitope": 15,
}

VACCINE_GATES = [
    "Sequence QC",
    "Homology filter",
    "MHC I/MHC II/B-cell epitope prediction",
    "Antigenicity/allergenicity/toxicity filters",
    "Population coverage",
    "Construct validation",
]

MHC_METHODS = {"recommended", "recommended_epitope", "recommended_binding"}
BCELL_METHODS = {"Bepipred", "Bepipred-2.0"}
MHC_I_ALLELE_PATTERN = re.compile(r"^HLA-[A-Z0-9]+\*\d{2,3}:\d{2,3}$")
MHC_II_CHAIN_PATTERN = r"(?:HLA-)?[A-Z0-9]+\*\d{2,3}:\d{2,3}"
MHC_II_ALLELE_PATTERN = re.compile(
    rf"^{MHC_II_CHAIN_PATTERN}(?:/{MHC_II_CHAIN_PATTERN})?$"
)


@router.post("/plan")
def plan_vaccine_construct(
    project_name: str = Form("Candidate vaccine"),
    construct_type: str = Form("multi-epitope"),
    fasta: str = Form(...),
    user: User = Depends(get_current_user),
) -> dict:
    sequence = validate_protein_sequence(fasta, min_length=9)

    window_size = WINDOW_BY_CONSTRUCT.get(construct_type, 15)
    step = max(window_size, len(sequence) // 6)
    windows = []

    for start in range(0, max(len(sequence) - window_size + 1, 1), step):
        if len(windows) >= 6:
            break
        peptide = sequence[start : start + window_size]
        if len(peptide) == window_size:
            windows.append(
                {
                    "range": f"{start + 1}-{start + window_size}",
                    "sequence": peptide,
                }
            )

    composition = {
        amino_acid: sequence.count(amino_acid)
        for amino_acid in sorted(VALID_AMINO_ACIDS)
        if sequence.count(amino_acid)
    }

    return {
        "projectName": project_name.strip() or "Candidate vaccine",
        "constructType": construct_type,
        "length": len(sequence),
        "windows": windows,
        "composition": composition,
        "requiredGates": VACCINE_GATES,
    }


@router.post("/predict/mhc")
def predict_mhc(
    fasta: str = Form(...),
    mhc_class: str = Form("mhc-i"),
    alleles: str = Form("HLA-A*02:01"),
    peptide_length: int = Form(9),
    method: str = Form("recommended_epitope"),
    rank_threshold: float | None = Form(None),
    user: User = Depends(get_current_user),
) -> dict:
    settings = get_settings()
    sequence = validate_protein_sequence(fasta, min_length=8)

    if mhc_class not in {"mhc-i", "mhc-ii"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MHC class must be 'mhc-i' or 'mhc-ii'.",
        )
    if method not in MHC_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported IEDB MHC method: {method}",
        )

    parsed_alleles = parse_hla_alleles(alleles, mhc_class=mhc_class)
    minimum_length, maximum_length = (8, 15) if mhc_class == "mhc-i" else (11, 30)
    if not minimum_length <= peptide_length <= maximum_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{mhc_class.upper()} peptide length must be between "
                f"{minimum_length} and {maximum_length}."
            ),
        )
    if len(sequence) < peptide_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The antigen sequence is shorter than the selected peptide length.",
        )

    threshold = rank_threshold
    if threshold is None:
        threshold = 1.0 if mhc_class == "mhc-i" else 10.0
    if not 0 < threshold <= 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rank threshold must be greater than 0 and no more than 100.",
        )

    workload = (len(sequence) - peptide_length + 1) * len(parsed_alleles)
    if workload > settings.iedb_max_predictions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Prediction workload is {workload:,}; the configured limit is "
                f"{settings.iedb_max_predictions:,}. Reduce sequence length or alleles."
            ),
        )

    try:
        return predict_mhc_binding(
            sequence=sequence,
            mhc_class=mhc_class,
            alleles=parsed_alleles,
            peptide_length=peptide_length,
            method=method,
            rank_threshold=threshold,
            result_limit=settings.iedb_result_limit,
        )
    except IEDBPredictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/predict/bcell")
def predict_bcell(
    fasta: str = Form(...),
    method: str = Form("Bepipred-2.0"),
    user: User = Depends(get_current_user),
) -> dict:
    sequence = validate_protein_sequence(fasta, min_length=10)
    if method not in BCELL_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported IEDB B-cell method: {method}",
        )

    try:
        return predict_bcell_epitopes(sequence=sequence, method=method)
    except IEDBPredictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/predict/processing")
def predict_processing(
    fasta: str = Form(...),
    alleles: str = Form("HLA-A*02:01"),
    peptide_length: int = Form(9),
    user: User = Depends(get_current_user),
) -> dict:
    settings = get_settings()
    sequence = validate_protein_sequence(fasta, min_length=8)
    parsed_alleles = parse_hla_alleles(alleles, mhc_class="mhc-i")
    if not 8 <= peptide_length <= 14:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MHC-I processing peptide length must be between 8 and 14.",
        )
    workload = (len(sequence) - peptide_length + 1) * len(parsed_alleles)
    if workload > settings.iedb_max_predictions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reduce sequence length or allele count for MHC-I processing.",
        )
    try:
        return predict_mhci_processing(
            sequence=sequence,
            alleles=parsed_alleles,
            peptide_length=peptide_length,
            result_limit=settings.iedb_result_limit,
        )
    except IEDBPredictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/source/search")
def search_antigen_source(
    query: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=10, ge=1, le=20),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        results = search_proteins(query.strip(), limit=limit)
    except NCBIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return {
        "provider": "NCBI Protein",
        "query": query,
        "results": results,
    }


@router.get("/source/fetch/{accession}")
def fetch_antigen_source(
    accession: str,
    user: User = Depends(get_current_user),
) -> dict:
    clean_accession = accession.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", clean_accession):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid NCBI protein accession.",
        )
    try:
        return fetch_protein_fasta(clean_accession)
    except NCBIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_vaccine_project(
    payload: VaccineProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    sequence = validate_protein_sequence(payload.fasta, min_length=9)
    project = VaccineProject(
        user_id=user.id,
        name=payload.name.strip() or "Candidate vaccine",
        source_accession=payload.source_accession.strip(),
        sequence=sequence,
        status="profiled",
        result_json={"sequenceProfile": profile_sequence(sequence)},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    persist_vaccine_artifacts(project, db)
    return serialize_vaccine_project(project)


@router.get("/projects")
def list_vaccine_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    projects = db.execute(
        select(VaccineProject)
        .where(VaccineProject.user_id == user.id)
        .order_by(desc(VaccineProject.updated_at))
        .limit(100)
    ).scalars()
    return [serialize_vaccine_project(project, include_results=False) for project in projects]


@router.get("/projects/{project_id}")
def get_vaccine_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return serialize_vaccine_project(owned_vaccine_project(db, user, project_id))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vaccine_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    project = owned_vaccine_project(db, user, project_id)
    db.delete(project)
    db.commit()


@router.post("/projects/{project_id}/analyze")
def analyze_vaccine_project(
    project_id: str,
    payload: VaccineAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    settings = get_settings()
    project = owned_vaccine_project(db, user, project_id)
    mhc_i_alleles = parse_hla_alleles(
        ",".join(payload.mhc_i_alleles),
        mhc_class="mhc-i",
    )
    mhc_ii_alleles = parse_hla_alleles(
        ",".join(payload.mhc_ii_alleles),
        mhc_class="mhc-ii",
    )
    validate_prediction_workload(
        project.sequence,
        payload.mhc_i_length,
        mhc_i_alleles,
        settings.iedb_max_predictions,
    )
    validate_prediction_workload(
        project.sequence,
        payload.mhc_ii_length,
        mhc_ii_alleles,
        settings.iedb_max_predictions,
    )

    project.status = "analyzing"
    project.config_json = payload.model_dump()
    db.add(project)
    db.commit()

    try:
        mhc_i = predict_mhc_binding(
            sequence=project.sequence,
            mhc_class="mhc-i",
            alleles=mhc_i_alleles,
            peptide_length=payload.mhc_i_length,
            method="recommended_epitope",
            rank_threshold=payload.mhc_i_rank_threshold,
            result_limit=settings.iedb_result_limit,
        )
        mhc_ii = predict_mhc_binding(
            sequence=project.sequence,
            mhc_class="mhc-ii",
            alleles=mhc_ii_alleles,
            peptide_length=payload.mhc_ii_length,
            method="recommended_epitope",
            rank_threshold=payload.mhc_ii_rank_threshold,
            result_limit=settings.iedb_result_limit,
        )
        bcell = predict_bcell_epitopes(
            sequence=project.sequence,
            method="Bepipred-2.0",
        )
        processing = (
            predict_mhci_processing(
                sequence=project.sequence,
                alleles=mhc_i_alleles,
                peptide_length=payload.mhc_i_length,
                result_limit=settings.iedb_result_limit,
            )
            if payload.include_processing and payload.mhc_i_length <= 14
            else None
        )
    except IEDBPredictionError as exc:
        project.status = "prediction_failed"
        db.add(project)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    result = {
        **(project.result_json or {}),
        "mhcI": mhc_i,
        "mhcII": mhc_ii,
        "bcell": bcell,
        "processing": processing,
    }
    result["candidates"] = rank_epitope_candidates(
        mhc_i=mhc_i,
        mhc_ii=mhc_ii,
        bcell=bcell,
        processing=processing,
        limit=payload.candidate_limit,
    )
    result["validationGaps"] = validation_gaps()
    project.result_json = result
    project.status = "analyzed"
    persist_vaccine_artifacts(project, db)
    return serialize_vaccine_project(project)


@router.post("/projects/{project_id}/construct")
def build_vaccine_construct(
    project_id: str,
    payload: VaccineConstructRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project = owned_vaccine_project(db, user, project_id)
    candidates = (project.result_json or {}).get("candidates", [])
    try:
        construct = assemble_construct(
            candidates,
            payload.candidate_ids,
            add_start_methionine=payload.add_start_methionine,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    project.result_json = {**(project.result_json or {}), "construct": construct}
    project.status = "construct_ready"
    persist_vaccine_artifacts(project, db)
    return serialize_vaccine_project(project)


@router.post("/projects/{project_id}/blast")
def submit_project_blast(
    project_id: str,
    database: str = Form("swissprot"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if database not in {"swissprot", "nr", "refseq_protein"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BLAST database must be swissprot, nr, or refseq_protein.",
        )
    project = owned_vaccine_project(db, user, project_id)
    try:
        submission = submit_blastp(project.sequence, database=database)
    except NCBIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    project.result_json = {
        **(project.result_json or {}),
        "blast": {**submission, "status": "submitted", "hits": []},
    }
    persist_vaccine_artifacts(project, db)
    return project.result_json["blast"]


@router.get("/projects/{project_id}/blast")
def poll_project_blast(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    project = owned_vaccine_project(db, user, project_id)
    blast = (project.result_json or {}).get("blast") or {}
    rid = blast.get("rid")
    if not rid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No BLAST search has been submitted for this project.",
        )
    try:
        result = get_blastp_result(rid)
    except NCBIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    project.result_json = {
        **(project.result_json or {}),
        "blast": {**blast, **result},
    }
    persist_vaccine_artifacts(project, db)
    return project.result_json["blast"]


@router.get("/projects/{project_id}/files/{kind}")
def get_vaccine_file(
    project_id: str,
    kind: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    project = owned_vaccine_project(db, user, project_id)
    files = (project.result_json or {}).get("files", {})
    path_map = {
        "report": files.get("report", ""),
        "result-json": files.get("resultJson", ""),
        "antigen-fasta": files.get("antigenFasta", ""),
        "construct-fasta": files.get("constructFasta", ""),
        "dna-fasta": files.get("dnaFasta", ""),
    }
    raw_path = path_map.get(kind)
    if not raw_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vaccine project file is not available.",
        )
    path = assert_inside_storage(Path(raw_path))
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vaccine project file is missing.",
        )
    media_type = "application/json" if kind == "result-json" else "text/plain"
    if kind == "report":
        media_type = "text/markdown"
    return FileResponse(path, media_type=media_type, filename=path.name)


def clean_protein_sequence(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if not line.strip().startswith(">")]
    return "".join(lines).replace(" ", "").replace("\t", "").upper()


def validate_protein_sequence(value: str, *, min_length: int) -> str:
    sequence = clean_protein_sequence(value)
    invalid = sorted({letter for letter in sequence if letter not in VALID_AMINO_ACIDS})

    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported amino acid symbols: {', '.join(invalid)}",
        )
    if len(sequence) < min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Enter a protein FASTA sequence with at least {min_length} amino acids."
            ),
        )

    maximum = get_settings().vaccine_max_sequence_aa
    if len(sequence) > maximum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Antigen sequence exceeds the configured {maximum:,} amino-acid limit.",
        )
    return sequence


def parse_hla_alleles(value: str, *, mhc_class: str) -> list[str]:
    alleles = []
    for line in value.splitlines():
        alleles.extend(item.strip() for item in line.split(",") if item.strip())
    alleles = list(dict.fromkeys(alleles))

    if not alleles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter at least one HLA allele.",
        )
    if len(alleles) > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A maximum of 12 HLA alleles can be submitted per request.",
        )

    pattern = MHC_I_ALLELE_PATTERN if mhc_class == "mhc-i" else MHC_II_ALLELE_PATTERN
    invalid = [allele for allele in alleles if not pattern.fullmatch(allele)]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid human HLA allele format: {', '.join(invalid)}",
        )
    return alleles


def owned_vaccine_project(
    db: Session,
    user: User,
    project_id: str,
) -> VaccineProject:
    project = db.get(VaccineProject, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vaccine project not found.",
        )
    return project


def serialize_vaccine_project(
    project: VaccineProject,
    *,
    include_results: bool = True,
) -> dict:
    payload = {
        "id": project.id,
        "name": project.name,
        "sourceAccession": project.source_accession,
        "sequence": project.sequence if include_results else "",
        "length": len(project.sequence),
        "status": project.status,
        "config": project.config_json or {},
        "createdAt": project.created_at,
        "updatedAt": project.updated_at,
        "files": {
            "report": f"/vaccine/projects/{project.id}/files/report"
            if project.report_path
            else None,
            "resultJson": f"/vaccine/projects/{project.id}/files/result-json"
            if (project.result_json or {}).get("files", {}).get("resultJson")
            else None,
            "antigenFasta": f"/vaccine/projects/{project.id}/files/antigen-fasta",
            "constructFasta": f"/vaccine/projects/{project.id}/files/construct-fasta"
            if (project.result_json or {}).get("files", {}).get("constructFasta")
            else None,
            "dnaFasta": f"/vaccine/projects/{project.id}/files/dna-fasta"
            if (project.result_json or {}).get("files", {}).get("dnaFasta")
            else None,
        },
    }
    if include_results:
        payload["results"] = project.result_json or {}
    return payload


def persist_vaccine_artifacts(project: VaccineProject, db: Session) -> None:
    settings = get_settings()
    output_dir = settings.storage_dir / "vaccine" / project.id
    files = write_vaccine_artifacts(project, output_dir)
    project.report_path = files["report"]
    project.result_json = {**(project.result_json or {}), "files": files}
    db.add(project)
    db.commit()
    db.refresh(project)


def validate_prediction_workload(
    sequence: str,
    peptide_length: int,
    alleles: list[str],
    maximum: int,
) -> None:
    if len(sequence) < peptide_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The antigen is shorter than a selected peptide length.",
        )
    workload = (len(sequence) - peptide_length + 1) * len(alleles)
    if workload > maximum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Prediction workload is {workload:,}; the configured maximum is "
                f"{maximum:,}."
            ),
        )


def validation_gaps() -> list[dict]:
    return [
        {
            "gate": "Conservation and host homology",
            "status": "external_validation_required",
            "handoff": "NCBI BLAST is integrated; expert interpretation and strain panels remain required.",
        },
        {
            "gate": "Antigenicity, allergenicity, and toxicity",
            "status": "external_validation_required",
            "handoff": "No supported licensed provider API is configured. Do not infer these outcomes from sequence rules.",
        },
        {
            "gate": "Population coverage",
            "status": "external_validation_required",
            "handoff": "Use IEDB Population Coverage or a validated HLA frequency dataset with the selected alleles.",
        },
        {
            "gate": "Structure and immune simulation",
            "status": "external_validation_required",
            "handoff": "Export FASTA for AlphaFold/ColabFold, protein-protein docking, and validated immune simulation.",
        },
    ]
