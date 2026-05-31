import json
from pathlib import Path

from app.models import DockingJob


def generate_reports(job: DockingJob, result: dict, report_path: Path, json_path: Path) -> None:
    modes = result.get("modes", [])
    contacts = result.get("contacts", [])
    warnings = result.get("warnings", [])
    best = result.get("best_affinity_kcal_mol")

    lines = [
        f"# MoliDock Pro Docking Report: {job.ligand_name} vs {job.protein_name}",
        "",
        "## Summary",
        f"- Job ID: {job.id}",
        f"- Protein: {job.protein_name}",
        f"- Ligand: {job.ligand_name}",
        f"- Status: {job.status.value}",
        f"- Best affinity: {best if best is not None else 'unavailable'} kcal/mol",
        "",
        "## Docking Modes",
    ]

    if modes:
        lines.extend(["| Mode | Affinity (kcal/mol) | RMSD LB | RMSD UB |", "|---:|---:|---:|---:|"])
        for mode in modes:
            lines.append(
                f"| {mode.get('mode')} | {mode.get('affinity_kcal_mol')} | "
                f"{mode.get('rmsd_lb', '')} | {mode.get('rmsd_ub', '')} |"
            )
    else:
        lines.append("No docking modes were parsed.")

    lines.extend(["", "## Geometric Contact Screen"])
    if contacts:
        lines.extend(
            [
                "| Residue | Ligand Atom | Receptor Atom | Distance (A) | Type |",
                "|---|---|---|---:|---|",
            ]
        )
        for contact in contacts[:50]:
            residue = f"{contact.get('residue')} {contact.get('chain')}{contact.get('residue_number')}"
            lines.append(
                f"| {residue} | {contact.get('ligand_atom')} | {contact.get('receptor_atom')} | "
                f"{contact.get('distance_angstrom')} | {contact.get('interaction_type')} |"
            )
    else:
        lines.append("No close receptor-ligand contacts were detected by the simple geometric screen.")

    lines.extend(
        [
            "",
            "## Scientific Notes",
            "- Docking scores are model outputs, not binding constants or clinical efficacy evidence.",
            "- Protein protonation, ligand tautomer state, grid placement, cofactors, waters, and receptor flexibility can change results.",
            "- The contact table is a lightweight geometric screen. Use a validated interaction profiler before publication.",
        ]
    )

    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

