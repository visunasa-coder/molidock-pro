from pathlib import Path

from app.services.grid import calculate_bounding_box_grid, resolve_docking_box


def atom_line(serial: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d}  C   LIG A   1    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  0.00  0.00     0.000 C"
    )


def write_structure(path: Path, coordinates: list[tuple[float, float, float]]) -> Path:
    lines = [atom_line(index, *coordinate) for index, coordinate in enumerate(coordinates, start=1)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_bounding_box_grid_uses_midpoint_and_padding(tmp_path: Path) -> None:
    receptor = write_structure(
        tmp_path / "receptor.pdbqt",
        [(-10.0, 0.0, 5.0), (30.0, 20.0, 25.0)],
    )

    grid = calculate_bounding_box_grid(receptor)

    assert grid == {
        "method": "receptor_bounding_box",
        "center_x": 10.0,
        "size_x": 50.0,
        "center_y": 10.0,
        "size_y": 30.0,
        "center_z": 15.0,
        "size_z": 30.0,
    }


def test_bounding_box_grid_caps_each_dimension(tmp_path: Path) -> None:
    receptor = write_structure(
        tmp_path / "large-receptor.pdbqt",
        [(-100.0, -80.0, -70.0), (100.0, 80.0, 70.0)],
    )

    grid = calculate_bounding_box_grid(receptor)

    assert grid["center_x"] == 0.0
    assert grid["center_y"] == 0.0
    assert grid["center_z"] == 0.0
    assert grid["size_x"] == 120.0
    assert grid["size_y"] == 120.0
    assert grid["size_z"] == 120.0


def test_resolve_docking_box_replaces_only_legacy_default(tmp_path: Path) -> None:
    receptor = write_structure(
        tmp_path / "receptor.pdbqt",
        [(90.0, 100.0, 110.0), (110.0, 130.0, 150.0)],
    )
    submitted = {
        "center_x": 0.0,
        "center_y": 0.0,
        "center_z": 0.0,
        "size_x": 20.0,
        "size_y": 20.0,
        "size_z": 20.0,
        "exhaustiveness": 16,
        "num_modes": 10,
    }

    resolved, generated = resolve_docking_box(submitted, receptor)

    assert generated is True
    assert resolved["center_x"] == 100.0
    assert resolved["center_y"] == 115.0
    assert resolved["center_z"] == 130.0
    assert resolved["size_x"] == 30.0
    assert resolved["size_y"] == 40.0
    assert resolved["size_z"] == 50.0
    assert resolved["exhaustiveness"] == 16
    assert resolved["num_modes"] == 10

    explicit = {**submitted, "center_x": 1.0}
    unchanged, generated = resolve_docking_box(explicit, receptor)

    assert generated is False
    assert unchanged == explicit
