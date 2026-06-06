import hashlib
import math
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import DockingJob, JobStatus
from app.services.grid import resolve_docking_box
from app.services.pdbqt import validate_ligand_pdbqt, validate_receptor_pdbqt
from app.services.reports import generate_reports


MODE_RE = re.compile(r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)?\s+(-?\d+(?:\.\d+)?)?")
ATOM_RECORDS = {"ATOM", "HETATM"}
HBOND_ELEMENTS = {"N", "O", "S"}
HYDROPHOBIC_ELEMENTS = {"C", "A"}


class DockingDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Atom:
    atom_name: str
    residue: str
    chain: str
    residue_number: str
    element: str
    x: float
    y: float
    z: float


def execute_docking_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(DockingJob, job_id)
        if not job:
            return

        _set_job_status(db, job, JobStatus.running)

        pipeline = DockingPipeline(get_settings())
        result = pipeline.run(job)

        job.result_json = result
        job.status = JobStatus.completed
        job.pose_path = result.get("pose_path", "")
        job.report_path = result.get("report_path", "")
        job.log_path = result.get("log_path", "")
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = ""

        db.add(job)
        db.commit()

    except Exception as exc:
        if "job" in locals() and job:
            job.status = JobStatus.failed
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.add(job)
            db.commit()
    finally:
        db.close()


def _set_job_status(db: Session, job: DockingJob, status: JobStatus) -> None:
    job.status = status
    db.add(job)
    db.commit()
    db.refresh(job)


class DockingPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, job: DockingJob) -> dict:
        payload = dict(job.input_json or {})
        payload["box"] = dict(payload["box"])

        work_dir = Path(job.work_dir)
        prepared_dir = work_dir / "prepared"
        output_dir = work_dir / "outputs"

        prepared_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []

        receptor = self._prepare_receptor(Path(payload["protein_path"]), prepared_dir, warnings)
        payload["box"], generated_grid = resolve_docking_box(payload["box"], receptor)
        if generated_grid:
            warnings.append(
                "Docking grid was generated from the prepared receptor bounding box "
                "because the submitted grid matched the legacy default."
            )
        ligand = self._prepare_ligand(Path(payload["ligand_path"]), prepared_dir, warnings)

        pose_path = output_dir / "pose.pdbqt"
        log_path = output_dir / "vina.log"
        report_path = output_dir / "report.md"
        json_path = output_dir / "result.json"

        run_result = self._run_vina(receptor, ligand, pose_path, log_path, payload)

        modes = parse_vina_modes(log_path.read_text(encoding="utf-8", errors="ignore"))

        if not modes:
            modes = run_result.get("modes", [])

        if not modes:
            raise RuntimeError("Vina completed but no docking modes were parsed from the log.")

        contacts = find_contacts(receptor, pose_path)
        warnings.extend(run_result.get("warnings", []))

        result = {
            "job_id": job.id,
            "engine": run_result.get("engine", "AutoDock Vina"),
            "best_affinity_kcal_mol": modes[0]["affinity_kcal_mol"],
            "modes": modes,
            "contacts": contacts,
            "warnings": warnings,
            "pose_path": str(pose_path),
            "receptor_path": str(receptor),
            "report_path": str(report_path),
            "log_path": str(log_path),
            "result_json_path": str(json_path),
            "box": payload["box"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        generate_reports(job, result, report_path, json_path)
        return result

    def _prepare_receptor(self, source: Path, prepared_dir: Path, warnings: list[str]) -> Path:
        output = prepared_dir / "receptor.pdbqt"

        if source.suffix.lower() == ".pdbqt":
            shutil.copyfile(source, output)
            validate_receptor_pdbqt(output)
            return output

        if self.settings.prepare_receptor_binary:
            cmd = self._command(self.settings.prepare_receptor_binary) + [
                "-r",
                str(source),
                "-o",
                str(output),
                "-A",
                "hydrogens",
            ]
            self._run_command(cmd, "receptor preparation")
            validate_receptor_pdbqt(output)
            return output

        if shutil.which(self._command_name(self.settings.obabel_binary)):
            warnings.append(
                "Receptor was converted with Open Babel because PREPARE_RECEPTOR_BINARY was not configured. "
                "Validate protonation, charges, metals, cofactors, and waters before relying on results."
            )
            cmd = self._command(self.settings.obabel_binary) + [
                str(source),
                "-O",
                str(output),
                "-xr",
                "-h",
            ]
            self._run_command(cmd, "Open Babel receptor conversion")
            validate_receptor_pdbqt(output)
            return output

        raise DockingDependencyError(
            "Upload a receptor already in PDBQT format, or configure PREPARE_RECEPTOR_BINARY/Open Babel."
        )

    def _prepare_ligand(self, source: Path, prepared_dir: Path, warnings: list[str]) -> Path:
        output = prepared_dir / "ligand.pdbqt"

        if source.suffix.lower() == ".pdbqt":
            shutil.copyfile(source, output)
            validate_ligand_pdbqt(output)
            return output

        if not shutil.which(self._command_name(self.settings.obabel_binary)):
            raise DockingDependencyError("Open Babel is required to prepare non-PDBQT ligands.")

        warnings.append(
            "Ligand was prepared with Open Babel. Review protonation, tautomer, stereochemistry, and charge state."
        )

        cmd = self._command(self.settings.obabel_binary) + [
            str(source),
            "-O",
            str(output),
            "--gen3d",
            "-h",
        ]
        self._run_command(cmd, "Open Babel ligand preparation")
        validate_ligand_pdbqt(output)
        return output

    def _run_vina(
        self,
        receptor: Path,
        ligand: Path,
        pose_path: Path,
        log_path: Path,
        payload: dict,
    ) -> dict:
        vina_binary = self.settings.vina_binary

        if not Path(vina_binary).exists():
            if self.settings.allow_demo_docking:
                return self._demo_docking(receptor, ligand, pose_path, log_path)

            raise DockingDependencyError(
                f"AutoDock Vina binary '{self.settings.vina_binary}' was not found. "
                "Install Vina or set VINA_BINARY to the executable path."
            )

        box = payload["box"]

        required = [
            "center_x",
            "center_y",
            "center_z",
            "size_x",
            "size_y",
            "size_z",
            "exhaustiveness",
            "num_modes",
        ]

        for key in required:
            if key not in box or box[key] in [None, ""]:
                raise ValueError(f"Missing or empty docking box value: {key}")

        for key in required:
            if key in ["exhaustiveness", "num_modes"]:
                box[key] = int(box[key])
            else:
                box[key] = float(box[key])

        for key in required:
            print(f"{key} = {box.get(key)}")

        cpu = min(
            int(payload.get("cpu", self.settings.max_parallel_cpu)),
            self.settings.max_parallel_cpu,
        )

        cmd = self._command(self.settings.vina_binary) + [
            "--receptor",
            str(receptor),
            "--ligand",
            str(ligand),
            "--center_x",
            str(box["center_x"]),
            "--center_y",
            str(box["center_y"]),
            "--center_z",
            str(box["center_z"]),
            "--size_x",
            str(box["size_x"]),
            "--size_y",
            str(box["size_y"]),
            "--size_z",
            str(box["size_z"]),
            "--exhaustiveness",
            str(box["exhaustiveness"]),
            "--num_modes",
            str(box["num_modes"]),
            "--cpu",
            str(max(cpu, 1)),
            "--out",
            str(pose_path),
        ]

        completed = self._run_command(cmd, "AutoDock Vina docking")

        if not pose_path.exists():
            raise RuntimeError("AutoDock Vina did not produce a pose file.")

        if not log_path.exists():
            log_path.write_text(
                (completed.stdout or "") + "\n" + (completed.stderr or ""),
                encoding="utf-8",
            )

        return {"engine": "AutoDock Vina"}

    def _demo_docking(self, receptor: Path, ligand: Path, pose_path: Path, log_path: Path) -> dict:
        shutil.copyfile(ligand, pose_path)

        digest = hashlib.sha256(
            (receptor.read_text(errors="ignore") + ligand.read_text(errors="ignore")).encode()
        ).hexdigest()

        scaled = int(digest[:6], 16) / 0xFFFFFF
        affinity = round(-5.5 - scaled * 4.0, 3)

        log_path.write_text(
            "\n".join(
                [
                    "DEMO MODE - not a scientific docking result",
                    "-----+------------+----------+----------",
                    "mode | affinity   | dist from best mode",
                    "     | (kcal/mol) | rmsd l.b.| rmsd u.b.",
                    f"   1       {affinity}      0.000      0.000",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        return {
            "engine": "MoliDock deterministic demo",
            "modes": [
                {
                    "mode": 1,
                    "affinity_kcal_mol": affinity,
                    "rmsd_lb": 0.0,
                    "rmsd_ub": 0.0,
                }
            ],
            "warnings": [
                "Demo docking is enabled. Results are placeholders and must not be sold as scientific output."
            ],
        }

    def _run_command(self, cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.settings.job_timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DockingDependencyError(f"Required command for {label} was not found: {cmd[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{label} exceeded {self.settings.job_timeout_seconds} seconds") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
            raise RuntimeError(f"{label} failed with exit code {completed.returncode}: {detail}")

        return completed

    @staticmethod
    def _command(binary: str) -> list[str]:
        return shlex.split(binary) if binary else []

    @staticmethod
    def _command_name(binary: str) -> str:
        parts = shlex.split(binary)
        return parts[0] if parts else binary


def parse_vina_modes(log_text: str) -> list[dict]:
    modes: list[dict] = []

    for line in log_text.splitlines():
        match = MODE_RE.match(line)

        if not match:
            continue

        mode = int(match.group(1))

        if mode <= 0 or mode > 100:
            continue

        affinity = float(match.group(2))
        rmsd_lb = float(match.group(3)) if match.group(3) is not None else None
        rmsd_ub = float(match.group(4)) if match.group(4) is not None else None

        modes.append(
            {
                "mode": mode,
                "affinity_kcal_mol": affinity,
                "rmsd_lb": rmsd_lb,
                "rmsd_ub": rmsd_ub,
            }
        )

    return modes


def parse_atoms(path: Path) -> list[Atom]:
    atoms: list[Atom] = []

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        record = line[:6].strip()

        if record not in ATOM_RECORDS:
            continue

        try:
            atom_name = line[12:16].strip() or "X"
            residue = line[17:20].strip() or "UNK"
            chain = line[21:22].strip() or "-"
            residue_number = line[22:26].strip() or "0"

            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])

        except (ValueError, IndexError):
            parts = line.split()

            if len(parts) < 8:
                continue

            atom_name = parts[2] if len(parts) > 2 else "X"
            residue = parts[3] if len(parts) > 3 else "UNK"
            chain = parts[4] if len(parts) > 4 else "-"
            residue_number = parts[5] if len(parts) > 5 else "0"

            try:
                x, y, z = float(parts[6]), float(parts[7]), float(parts[8])
            except (ValueError, IndexError):
                continue

        element = infer_element(atom_name)

        if element == "H":
            continue

        atoms.append(
            Atom(
                atom_name,
                residue,
                chain,
                residue_number,
                element,
                x,
                y,
                z,
            )
        )

    return atoms


def infer_element(atom_name: str) -> str:
    cleaned = "".join(ch for ch in atom_name.upper() if ch.isalpha())

    if not cleaned:
        return "X"

    if len(cleaned) >= 2 and cleaned[:2] in {
        "CL",
        "BR",
        "NA",
        "MG",
        "ZN",
        "FE",
        "CA",
        "MN",
        "CU",
    }:
        return cleaned[:2]

    return cleaned[0]


def find_contacts(receptor_path: Path, pose_path: Path, max_contacts: int = 75) -> list[dict]:
    receptor_atoms = parse_atoms(receptor_path)
    ligand_atoms = parse_atoms(pose_path)

    contacts: list[dict] = []
    cutoff_sq = 5.0 * 5.0

    for ligand in ligand_atoms:
        for receptor in receptor_atoms:
            distance_sq = (
                (ligand.x - receptor.x) ** 2
                + (ligand.y - receptor.y) ** 2
                + (ligand.z - receptor.z) ** 2
            )

            if distance_sq > cutoff_sq:
                continue

            distance = math.sqrt(distance_sq)
            interaction_type = classify_contact(ligand, receptor, distance)

            contacts.append(
                {
                    "residue": receptor.residue,
                    "chain": receptor.chain,
                    "residue_number": receptor.residue_number,
                    "ligand_atom": ligand.atom_name,
                    "receptor_atom": receptor.atom_name,
                    "distance_angstrom": round(distance, 3),
                    "interaction_type": interaction_type,
                }
            )

    contacts.sort(key=lambda item: item["distance_angstrom"])

    unique: dict[tuple[str, str, str, str], dict] = {}

    for contact in contacts:
        key = (
            contact["residue"],
            contact["chain"],
            contact["residue_number"],
            contact["interaction_type"],
        )

        unique.setdefault(key, contact)

        if len(unique) >= max_contacts:
            break

    return list(unique.values())


def classify_contact(ligand: Atom, receptor: Atom, distance: float) -> str:
    if distance <= 3.5 and ligand.element in HBOND_ELEMENTS and receptor.element in HBOND_ELEMENTS:
        return "possible_hbond"

    if distance <= 4.2 and ligand.element in HYDROPHOBIC_ELEMENTS and receptor.element in HYDROPHOBIC_ELEMENTS:
        return "hydrophobic_contact"

    if distance <= 4.0:
        return "polar_or_vdw_contact"

    return "nearby_contact"
