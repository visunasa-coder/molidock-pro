import subprocess
from pathlib import Path

OPEN_BABEL = r"C:\Program Files\OpenBabel-3.1.1\obabel.exe"


def sdf_to_pdbqt(sdf_path: str) -> str:
    input_path = Path(sdf_path)
    output_path = input_path.with_suffix(".pdbqt")

    result = subprocess.run(
        [
            OPEN_BABEL,
            str(input_path),
            "-O",
            str(output_path),
            "--gen3d",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return str(output_path)

def pdb_to_pdbqt(pdb_path: str) -> str:
    input_path = Path(pdb_path)
    output_path = input_path.with_suffix(".pdbqt")

    result = subprocess.run(
        [
            OPEN_BABEL,
            str(input_path),
            "-O",
            str(output_path),
            "-xr",
            "-p",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return str(output_path)