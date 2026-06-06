from dataclasses import dataclass
from pathlib import Path


ATOM_TAGS = {"ATOM", "HETATM"}
RECEPTOR_FORBIDDEN_TAGS = {"ROOT", "ENDROOT", "BRANCH", "ENDBRANCH", "TORSDOF"}
LIGAND_REQUIRED_TAGS = {"ROOT", "ENDROOT", "TORSDOF"}


class PDBQTValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PDBQTRecord:
    line_number: int
    tag: str
    line: str


def validate_receptor_pdbqt(path: Path) -> None:
    records = _read_records(path)
    _require_atoms(path, records)

    for record in records:
        if record.tag in RECEPTOR_FORBIDDEN_TAGS:
            raise PDBQTValidationError(
                f"Rigid receptor PDBQT contains ligand/flexible tag "
                f"{record.tag} at line {record.line_number}: {path}"
            )


def validate_ligand_pdbqt(path: Path) -> None:
    records = _read_records(path)
    _require_atoms(path, records)

    tags = {record.tag for record in records}
    missing = sorted(LIGAND_REQUIRED_TAGS - tags)
    if missing:
        raise PDBQTValidationError(
            f"Ligand PDBQT is missing required tag(s) {', '.join(missing)}: {path}"
        )

    torsdof = next(record for record in records if record.tag == "TORSDOF")
    parts = torsdof.line.split()
    if len(parts) != 2:
        raise PDBQTValidationError(
            f"Ligand PDBQT has invalid TORSDOF at line {torsdof.line_number}: {path}"
        )

    try:
        torsion_count = int(parts[1])
    except ValueError as exc:
        raise PDBQTValidationError(
            f"Ligand PDBQT has invalid TORSDOF at line {torsdof.line_number}: {path}"
        ) from exc

    if torsion_count < 0:
        raise PDBQTValidationError(
            f"Ligand PDBQT has negative TORSDOF at line {torsdof.line_number}: {path}"
        )


def _read_records(path: Path) -> list[PDBQTRecord]:
    if not path.is_file():
        raise PDBQTValidationError(f"PDBQT file does not exist: {path}")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise PDBQTValidationError(f"PDBQT file is not valid UTF-8 text: {path}") from exc

    records: list[PDBQTRecord] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        tag = stripped.split(maxsplit=1)[0].upper()
        records.append(PDBQTRecord(line_number=line_number, tag=tag, line=stripped))

    return records


def _require_atoms(path: Path, records: list[PDBQTRecord]) -> None:
    if not any(record.tag in ATOM_TAGS for record in records):
        raise PDBQTValidationError(f"PDBQT contains no ATOM or HETATM records: {path}")
