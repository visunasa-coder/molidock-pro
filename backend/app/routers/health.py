import shutil

from fastapi import APIRouter

from app.config import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "binaries": {
            "vina": bool(shutil.which(settings.vina_binary)),
            "obabel": bool(shutil.which(settings.obabel_binary)),
            "prepare_receptor": bool(settings.prepare_receptor_binary and shutil.which(settings.prepare_receptor_binary)),
        },
    }

