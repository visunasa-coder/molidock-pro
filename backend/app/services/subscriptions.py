from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DockingJob, Plan, User


def monthly_job_limit(user: User) -> int:
    settings = get_settings()
    limits = {
        Plan.free: settings.free_monthly_jobs,
        Plan.pro: settings.pro_monthly_jobs,
        Plan.lab: settings.lab_monthly_jobs,
        Plan.enterprise: 10**9,
    }
    return limits[user.plan]


def month_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def count_jobs_this_month(db: Session, user: User) -> int:
    statement = (
        select(func.count(DockingJob.id))
        .where(DockingJob.user_id == user.id)
        .where(DockingJob.created_at >= month_start_utc())
    )
    return int(db.execute(statement).scalar_one())


def ensure_can_start_job(db: Session, user: User) -> None:
    used = count_jobs_this_month(db, user)
    limit = monthly_job_limit(user)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Monthly docking quota reached for {user.plan.value} plan ({used}/{limit}). Upgrade required.",
        )

