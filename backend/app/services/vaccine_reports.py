import json
from pathlib import Path

from app.models import VaccineProject


def write_vaccine_artifacts(project: VaccineProject, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    report_path = output_dir / "report.md"
    antigen_path = output_dir / "antigen.fasta"
    construct_path = output_dir / "construct.fasta"
    dna_path = output_dir / "construct-dna.fasta"

    result = project.result_json or {}
    construct = result.get("construct") or {}
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    antigen_path.write_text(
        f">{project.source_accession or project.name}\n{wrap(project.sequence)}\n",
        encoding="utf-8",
    )
    if construct.get("proteinFasta"):
        construct_path.write_text(construct["proteinFasta"] + "\n", encoding="utf-8")
    if construct.get("dnaFasta"):
        dna_path.write_text(construct["dnaFasta"] + "\n", encoding="utf-8")
    report_path.write_text(build_markdown_report(project), encoding="utf-8")

    return {
        "report": str(report_path),
        "resultJson": str(result_path),
        "antigenFasta": str(antigen_path),
        "constructFasta": str(construct_path) if construct_path.exists() else "",
        "dnaFasta": str(dna_path) if dna_path.exists() else "",
    }


def build_markdown_report(project: VaccineProject) -> str:
    result = project.result_json or {}
    profile = result.get("sequenceProfile") or {}
    candidates = result.get("candidates") or []
    construct = result.get("construct") or {}
    blast = result.get("blast") or {}
    lines = [
        f"# MoliDock Pro Vaccine Design Report: {project.name}",
        "",
        "## Provenance",
        f"- Project ID: {project.id}",
        f"- Source accession: {project.source_accession or 'user supplied'}",
        f"- Antigen length: {len(project.sequence)} aa",
        f"- Project status: {project.status}",
        "",
        "## Sequence Profile",
        f"- Molecular weight: {profile.get('molecularWeightDa', 'not calculated')} Da",
        f"- Estimated pI: {profile.get('estimatedPI', 'not calculated')}",
        f"- GRAVY: {profile.get('gravy', 'not calculated')}",
        f"- Estimated charge at pH 7: {profile.get('estimatedChargePH7', 'not calculated')}",
        "",
        "## Predictor Summary",
    ]
    for key, label in (
        ("mhcI", "IEDB MHC-I"),
        ("mhcII", "IEDB MHC-II"),
        ("processing", "IEDB MHC-I processing"),
        ("bcell", "IEDB B-cell"),
    ):
        prediction = result.get(key)
        if prediction:
            count = prediction.get("totalPredictions", prediction.get("regionCount", 0))
            lines.append(
                f"- {label}: {count} outputs using {prediction.get('method', 'provider default')}"
            )

    lines.extend(["", "## Ranked Candidates"])
    if candidates:
        lines.extend(
            [
                "| Type | Allele | Range | Sequence | Rank % | Composite |",
                "|---|---|---:|---|---:|---:|",
            ]
        )
        for item in candidates[:50]:
            lines.append(
                f"| {item.get('type')} | {item.get('allele') or '-'} | "
                f"{item.get('start')}-{item.get('end')} | {item.get('sequence')} | "
                f"{item.get('rankPercent') if item.get('rankPercent') is not None else '-'} | "
                f"{item.get('compositeScore')} |"
            )
    else:
        lines.append("No ranked candidates are available.")

    if construct:
        lines.extend(
            [
                "",
                "## Construct",
                f"- Selected epitopes: {construct.get('epitopeCount')}",
                f"- Protein length: {len(construct.get('proteinSequence', ''))} aa",
                f"- DNA length: {len(construct.get('dnaSequence', ''))} nt",
                f"- GC content: {construct.get('gcPercent')}%",
                "",
                "```text",
                construct.get("proteinSequence", ""),
                "```",
            ]
        )

    if blast:
        lines.extend(
            [
                "",
                "## NCBI BLAST",
                f"- RID: {blast.get('rid', '')}",
                f"- Status: {blast.get('status', '')}",
                f"- Returned hits: {len(blast.get('hits', []))}",
            ]
        )

    lines.extend(
        [
            "",
            "## Required External Validation",
            "- Verify conservation across target strains and exclude clinically significant human homology.",
            "- Run validated antigenicity, allergenicity, and toxicity models under their applicable licenses.",
            "- Calculate population coverage with an authoritative HLA frequency dataset.",
            "- Validate construct expression, folding, accessibility, immunogenicity, safety, and efficacy experimentally.",
            "- Use protein-protein docking or immune simulation only with tools appropriate to those tasks; AutoDock Vina is not a substitute.",
            "",
            "## Scientific Limitations",
            "- Predictor scores prioritize candidates and do not establish protection or clinical efficacy.",
            "- Sequence liability flags are deterministic rules, not allergenicity or toxicity predictions.",
            "- The reverse-translated DNA uses fixed preferred codons and is not vendor-grade expression optimization.",
        ]
    )
    return "\n".join(lines) + "\n"


def wrap(sequence: str, width: int = 70) -> str:
    return "\n".join(sequence[index : index + width] for index in range(0, len(sequence), width))
