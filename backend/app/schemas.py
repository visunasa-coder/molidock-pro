from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import JobStatus, Plan


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=160)
    full_name: str = Field(default="", max_length=160)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    plan: Plan
    is_active: bool

    model_config = {"from_attributes": True}


class BoxParams(BaseModel):
    center_x: float = 0
    center_y: float = 0
    center_z: float = 0
    size_x: float = Field(default=20, gt=0, le=120)
    size_y: float = Field(default=20, gt=0, le=120)
    size_z: float = Field(default=20, gt=0, le=120)
    exhaustiveness: int = Field(default=16, ge=1, le=128)
    num_modes: int = Field(default=10, ge=1, le=50)

    @field_validator("center_x", "center_y", "center_z", "size_x", "size_y", "size_z")
    @classmethod
    def finite_numeric(cls, value: float) -> float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Docking box values must be finite numbers")
        return value


class Contact(BaseModel):
    residue: str
    chain: str
    residue_number: str
    ligand_atom: str
    receptor_atom: str
    distance_angstrom: float
    interaction_type: str


class DockingMode(BaseModel):
    mode: int
    affinity_kcal_mol: float
    rmsd_lb: float | None = None
    rmsd_ub: float | None = None


class JobFileLinks(BaseModel):
    pose: str | None = None
    receptor: str | None = None
    report: str | None = None
    log: str | None = None
    result_json: str | None = None


class DockingJobOut(BaseModel):
    id: str
    protein_name: str
    ligand_name: str
    status: JobStatus
    box: BoxParams | None = None
    best_affinity_kcal_mol: float | None = None
    modes: list[DockingMode] = []
    contacts: list[Contact] = []
    warnings: list[str] = []
    error_message: str = ""
    files: JobFileLinks = JobFileLinks()
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ADMETPrediction(BaseModel):
    smiles: str
    molecular_weight: float
    logp: float
    h_bond_donors: int
    h_bond_acceptors: int
    tpsa: float
    rotatable_bonds: int
    lipinski_violations: int
    soluble_signal: Literal["low", "moderate", "high"]
    oral_druglikeness_signal: Literal["weak", "moderate", "strong"]
    notes: list[str]
class VaccineProjectCreate(BaseModel):
    name: str = Field(default="Candidate vaccine", min_length=1, max_length=255)
    fasta: str = Field(min_length=1)
    source_accession: str = Field(default="", max_length=80)


class VaccineAnalysisRequest(BaseModel):
    mhc_i_alleles: list[str] = Field(
        default=["HLA-A*01:01", "HLA-A*02:01", "HLA-A*03:01", "HLA-A*24:02"],
        min_length=1,
        max_length=12,
    )
    mhc_ii_alleles: list[str] = Field(
        default=[
            "HLA-DRB1*01:01",
            "HLA-DRB1*04:01",
            "HLA-DRB1*07:01",
            "HLA-DRB1*15:01",
        ],
        min_length=1,
        max_length=12,
    )
    mhc_i_length: int = Field(default=9, ge=8, le=15)
    mhc_ii_length: int = Field(default=15, ge=11, le=30)
    mhc_i_rank_threshold: float = Field(default=1.0, gt=0, le=100)
    mhc_ii_rank_threshold: float = Field(default=10.0, gt=0, le=100)
    candidate_limit: int = Field(default=100, ge=1, le=500)
    include_processing: bool = True


class VaccineConstructRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=100)
    add_start_methionine: bool = True
