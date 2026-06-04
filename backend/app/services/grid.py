from pathlib import Path


def predict_grid_from_pdb(pdb_path: str) -> dict:
    path = Path(pdb_path)

    if not path.exists():
        raise FileNotFoundError(f"PDB file not found: {pdb_path}")

    xs = []
    ys = []
    zs = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])

                    xs.append(x)
                    ys.append(y)
                    zs.append(z)
                except ValueError:
                    continue

    if not xs:
        raise ValueError("No atom coordinates found in PDB file")

    return {
        "center_x": round(sum(xs) / len(xs), 4),
        "center_y": round(sum(ys) / len(ys), 4),
        "center_z": round(sum(zs) / len(zs), 4),
        "size_x": round(min(max(xs) - min(xs) + 10, 120), 2),
        "size_y": round(min(max(ys) - min(ys) + 10, 120), 2),
        "size_z": round(min(max(zs) - min(zs) + 10, 120), 2),
        "method": "protein_centroid_dynamic",
    }