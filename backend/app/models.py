import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Plan(str, enum.Enum):
    free = "free"
    pro = "pro"
    lab = "lab"
    enterprise = "enterprise"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[Plan] = mapped_column(Enum(Plan), default=Plan.free, nullable=False)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    jobs: Mapped[list["DockingJob"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    vaccine_projects: Mapped[list["VaccineProject"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class DockingJob(Base):
    __tablename__ = "docking_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    protein_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ligand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, nullable=False, index=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="")
    work_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    pose_path: Mapped[str] = mapped_column(String(1024), default="")
    report_path: Mapped[str] = mapped_column(String(1024), default="")
    log_path: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="jobs")


class VaccineProject(Base):
    __tablename__ = "vaccine_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_accession: Mapped[str] = mapped_column(String(80), default="")
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    report_path: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    owner: Mapped[User] = relationship(back_populates="vaccine_projects")

