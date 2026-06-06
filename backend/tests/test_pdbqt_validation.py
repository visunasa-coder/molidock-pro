from pathlib import Path

import pytest

from app.services.pdbqt import (
    PDBQTValidationError,
    validate_ligand_pdbqt,
    validate_receptor_pdbqt,
)


ATOM_LINE = "ATOM      1  C1  LIG A   1       0.000   0.000   0.000  0.00  0.00     0.000 C"


def write_pdbqt(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_receptor_pdbqt_rejects_root(tmp_path: Path) -> None:
    receptor = write_pdbqt(
        tmp_path / "receptor.pdbqt",
        ["ROOT", ATOM_LINE, "ENDROOT", "TORSDOF 0"],
    )

    with pytest.raises(PDBQTValidationError, match=r"tag ROOT at line 1"):
        validate_receptor_pdbqt(receptor)


def test_valid_ligand_pdbqt(tmp_path: Path) -> None:
    ligand = write_pdbqt(
        tmp_path / "ligand.pdbqt",
        ["ROOT", ATOM_LINE, "ENDROOT", "TORSDOF 0"],
    )

    validate_ligand_pdbqt(ligand)
