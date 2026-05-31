import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings


SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
ALLOWED_PROTEIN_EXTENSIONS = {".pdb", ".pdbqt"}
ALLOWED_LIGAND_EXTENSIONS = {".sdf", ".mol", ".mol2", ".pdb", ".pdbqt", ".smi", ".smiles"}


@dataclass(frozen=True)
class StoredFile:
    original_name: str
    path: Path
    sha256: str
    size_bytes: int


def safe_filename(name: str, fallback: str = "upload.dat") -> str:
    clean = SAFE_NAME_RE.sub("_", Path(name or fallback).name).strip("._")
    return clean or fallback


async def persist_upload(upload: UploadFile, destination_dir: Path, allowed_extensions: set[str]) -> StoredFile:
    settings = get_settings()
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(upload.filename or "upload.dat")
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type {suffix}. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    output_path = destination_dir / filename
    hasher = hashlib.sha256()
    size = 0

    with output_path.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > settings.upload_limit_bytes:
                output_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds {settings.max_upload_mb} MB limit",
                )
            hasher.update(chunk)
            handle.write(chunk)

    if size == 0:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    return StoredFile(original_name=filename, path=output_path, sha256=hasher.hexdigest(), size_bytes=size)


def assert_inside_storage(path: Path) -> Path:
    settings = get_settings()
    resolved = path.resolve()
    storage = settings.storage_dir.resolve()
    if storage not in resolved.parents and resolved != storage:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File is outside managed storage")
    return resolved

