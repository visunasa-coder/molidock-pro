from pathlib import Path


GRID_PADDING_ANGSTROM = 10.0
MAX_GRID_SIZE_ANGSTROM = 120.0
LEGACY_DEFAULT_CENTER = (0.0, 0.0, 0.0)
LEGACY_DEFAULT_SIZE = (20.0, 20.0, 20.0)
GRID_AXES = ("x", "y", "z")


def calculate_bounding_box_grid(
    structure_path: str | Path,
    padding: float = GRID_PADDING_ANGSTROM,
    max_size: float = MAX_GRID_SIZE_ANGSTROM,
) -> dict:
    path = Path(structure_path)

    if not path.is_file():
        raise FileNotFoundError(f"Structure file not found: {path}")
    if padding < 0:
        raise ValueError("Grid padding must be non-negative")
    if max_size <= 0:
        raise ValueError("Maximum grid size must be positive")

    coordinates = _read_coordinates(path)
    if not coordinates:
        raise ValueError(f"No atom coordinates found in structure file: {path}")

    grid: dict[str, float | str] = {"method": "receptor_bounding_box"}
    for index, axis in enumerate(GRID_AXES):
        values = [coordinate[index] for coordinate in coordinates]
        minimum = min(values)
        maximum = max(values)
        grid[f"center_{axis}"] = round((minimum + maximum) / 2, 4)
        grid[f"size_{axis}"] = round(min(maximum - minimum + padding, max_size), 2)

    return grid


def resolve_docking_box(box: dict, receptor_path: str | Path) -> tuple[dict, bool]:
    resolved = dict(box)
    if not is_legacy_default_box(resolved):
        return resolved, False

    generated = calculate_bounding_box_grid(receptor_path)
    for axis in GRID_AXES:
        resolved[f"center_{axis}"] = generated[f"center_{axis}"]
        resolved[f"size_{axis}"] = generated[f"size_{axis}"]
    resolved["method"] = generated["method"]
    return resolved, True


def is_legacy_default_box(box: dict) -> bool:
    try:
        center = tuple(float(box[f"center_{axis}"]) for axis in GRID_AXES)
        size = tuple(float(box[f"size_{axis}"]) for axis in GRID_AXES)
    except (KeyError, TypeError, ValueError):
        return False

    return center == LEGACY_DEFAULT_CENTER and size == LEGACY_DEFAULT_SIZE


def predict_grid_from_pdb(pdb_path: str) -> dict:
    return calculate_bounding_box_grid(pdb_path)


def _read_coordinates(path: Path) -> list[tuple[float, float, float]]:
    coordinates: list[tuple[float, float, float]] = []

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            coordinates.append(
                (
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54]),
                )
            )
        except ValueError:
            continue

    return coordinates
