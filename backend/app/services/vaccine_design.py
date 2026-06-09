import hashlib
import math
from collections import Counter


RESIDUE_MASS = {
    "A": 71.0788,
    "C": 103.1388,
    "D": 115.0886,
    "E": 129.1155,
    "F": 147.1766,
    "G": 57.0519,
    "H": 137.1411,
    "I": 113.1594,
    "K": 128.1741,
    "L": 113.1594,
    "M": 131.1926,
    "N": 114.1038,
    "P": 97.1167,
    "Q": 128.1307,
    "R": 156.1875,
    "S": 87.0782,
    "T": 101.1051,
    "V": 99.1326,
    "W": 186.2132,
    "Y": 163.1760,
}

HYDROPATHY = {
    "A": 1.8,
    "C": 2.5,
    "D": -3.5,
    "E": -3.5,
    "F": 2.8,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "K": -3.9,
    "L": 3.8,
    "M": 1.9,
    "N": -3.5,
    "P": -1.6,
    "Q": -3.5,
    "R": -4.5,
    "S": -0.8,
    "T": -0.7,
    "V": 4.2,
    "W": -0.9,
    "Y": -1.3,
}

PREFERRED_CODONS = {
    "A": "GCC",
    "C": "TGC",
    "D": "GAC",
    "E": "GAG",
    "F": "TTC",
    "G": "GGC",
    "H": "CAC",
    "I": "ATC",
    "K": "AAG",
    "L": "CTG",
    "M": "ATG",
    "N": "AAC",
    "P": "CCC",
    "Q": "CAG",
    "R": "CGC",
    "S": "AGC",
    "T": "ACC",
    "V": "GTG",
    "W": "TGG",
    "Y": "TAC",
}

LINKERS = {
    "mhc-i": "AAY",
    "mhc-ii": "GPGPG",
    "b-cell": "KK",
}


def profile_sequence(sequence: str) -> dict:
    counts = Counter(sequence)
    length = len(sequence)
    molecular_weight = sum(RESIDUE_MASS[residue] for residue in sequence) + 18.0153
    gravy = sum(HYDROPATHY[residue] for residue in sequence) / length
    aromaticity = sum(counts[residue] for residue in "FWY") / length
    p_i = estimate_isoelectric_point(sequence)
    hydrophobic_regions = find_hydrophobic_regions(sequence)
    low_complexity_regions = find_low_complexity_regions(sequence)
    glycosylation_sites = [
        index + 1
        for index in range(len(sequence) - 2)
        if sequence[index] == "N"
        and sequence[index + 1] != "P"
        and sequence[index + 2] in {"S", "T"}
    ]
    warnings = []
    if hydrophobic_regions:
        warnings.append(
            "Hydrophobic windows may indicate transmembrane or aggregation-prone segments."
        )
    if low_complexity_regions:
        warnings.append("Low-complexity windows may reduce construct stability or specificity.")
    if counts["C"] > max(4, length * 0.05):
        warnings.append("High cysteine content may promote unintended disulfide pairing.")
    if abs(net_charge(sequence, 7.0)) > max(10, length * 0.2):
        warnings.append("High predicted net charge may complicate expression or formulation.")

    return {
        "length": length,
        "molecularWeightDa": round(molecular_weight, 2),
        "gravy": round(gravy, 4),
        "aromaticity": round(aromaticity, 4),
        "estimatedPI": round(p_i, 2),
        "estimatedChargePH7": round(net_charge(sequence, 7.0), 2),
        "composition": dict(sorted(counts.items())),
        "glycosylationMotifs": glycosylation_sites,
        "hydrophobicRegions": hydrophobic_regions,
        "lowComplexityRegions": low_complexity_regions,
        "warnings": warnings,
        "methodNote": (
            "Physicochemical values are deterministic sequence calculations. Liability "
            "flags are transparent rules, not allergenicity or toxicity predictions."
        ),
    }


def rank_epitope_candidates(
    *,
    mhc_i: dict,
    mhc_ii: dict,
    bcell: dict,
    processing: dict | None = None,
    limit: int = 100,
) -> list[dict]:
    processing_map = {}
    if processing:
        for item in processing.get("results", []):
            processing_map[(item["allele"], item["start"], item["peptide"])] = item

    regions = bcell.get("regions", [])
    candidates = []
    seen = set()
    for source, prediction in (("mhc-i", mhc_i), ("mhc-ii", mhc_ii)):
        for item in prediction.get("results", []):
            if not item.get("isBinder"):
                continue
            key = (source, item["allele"], item["start"], item["peptide"])
            if key in seen:
                continue
            seen.add(key)
            overlap = max(
                (
                    max(
                        0,
                        min(item["end"], region["end"])
                        - max(item["start"], region["start"])
                        + 1,
                    )
                    / item["length"]
                    for region in regions
                ),
                default=0,
            )
            process = processing_map.get(
                (item["allele"], item["start"], item["peptide"])
            )
            rank_score = max(0.0, 100.0 - min(item["rankPercent"], 100.0))
            processing_bonus = (
                max(0.0, min(15.0, (process["totalScore"] + 5) * 2))
                if process
                else 0.0
            )
            composite = rank_score + overlap * 15 + processing_bonus
            candidates.append(
                {
                    "id": candidate_id(source, item["allele"], item["start"], item["peptide"]),
                    "type": source,
                    "allele": item["allele"],
                    "start": item["start"],
                    "end": item["end"],
                    "sequence": item["peptide"],
                    "core": item["core"],
                    "rankPercent": item["rankPercent"],
                    "bcellOverlap": round(overlap, 3),
                    "processingScore": process["totalScore"] if process else None,
                    "compositeScore": round(composite, 3),
                    "sequenceProfile": profile_peptide(item["peptide"]),
                    "requiresSafetyReview": True,
                }
            )

    for region in regions:
        candidates.append(
            {
                "id": candidate_id("b-cell", "", region["start"], region["sequence"]),
                "type": "b-cell",
                "allele": "",
                "start": region["start"],
                "end": region["end"],
                "sequence": region["sequence"],
                "core": region["sequence"],
                "rankPercent": None,
                "bcellOverlap": 1.0,
                "processingScore": None,
                "compositeScore": round(70 + min(region["meanScore"], 1.0) * 20, 3),
                "sequenceProfile": profile_peptide(region["sequence"]),
                "requiresSafetyReview": True,
            }
        )

    candidates.sort(key=lambda item: (-item["compositeScore"], item["start"], item["sequence"]))
    return candidates[:limit]


def assemble_construct(
    candidates: list[dict],
    selected_ids: list[str],
    *,
    add_start_methionine: bool = True,
) -> dict:
    by_id = {item["id"]: item for item in candidates}
    selected = [by_id[item_id] for item_id in selected_ids if item_id in by_id]
    if not selected:
        raise ValueError("Select at least one available epitope candidate.")

    parts = []
    previous_type = None
    for item in selected:
        if parts:
            parts.append(LINKERS.get(previous_type or item["type"], "GPGPG"))
        parts.append(item["sequence"])
        previous_type = item["type"]
    protein = "".join(parts)
    if add_start_methionine and not protein.startswith("M"):
        protein = f"M{protein}"

    dna = "".join(PREFERRED_CODONS[residue] for residue in protein) + "TAA"
    gc_count = dna.count("G") + dna.count("C")
    return {
        "selectedCandidateIds": [item["id"] for item in selected],
        "epitopeCount": len(selected),
        "proteinSequence": protein,
        "proteinFasta": f">molidock_multi_epitope_construct\n{wrap_sequence(protein)}",
        "dnaSequence": dna,
        "dnaFasta": f">molidock_codon_preferred_construct\n{wrap_sequence(dna)}",
        "gcPercent": round((gc_count / len(dna)) * 100, 2),
        "stopCodon": "TAA",
        "linkers": LINKERS,
        "profile": profile_sequence(protein),
        "methodNote": (
            "The DNA uses a fixed preferred-codon table and is a reverse-translation "
            "handoff, not a vendor-grade expression optimization."
        ),
    }


def profile_peptide(sequence: str) -> dict:
    return {
        "length": len(sequence),
        "gravy": round(sum(HYDROPATHY[item] for item in sequence) / len(sequence), 3),
        "estimatedChargePH7": round(net_charge(sequence, 7.0), 2),
        "cysteines": sequence.count("C"),
    }


def estimate_isoelectric_point(sequence: str) -> float:
    low, high = 0.0, 14.0
    for _ in range(50):
        middle = (low + high) / 2
        if net_charge(sequence, middle) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def net_charge(sequence: str, ph: float) -> float:
    counts = Counter(sequence)
    positive = (
        1 / (1 + 10 ** (ph - 9.69))
        + counts["K"] / (1 + 10 ** (ph - 10.5))
        + counts["R"] / (1 + 10 ** (ph - 12.4))
        + counts["H"] / (1 + 10 ** (ph - 6.0))
    )
    negative = (
        1 / (1 + 10 ** (2.34 - ph))
        + counts["D"] / (1 + 10 ** (3.86 - ph))
        + counts["E"] / (1 + 10 ** (4.25 - ph))
        + counts["C"] / (1 + 10 ** (8.33 - ph))
        + counts["Y"] / (1 + 10 ** (10.07 - ph))
    )
    return positive - negative


def find_hydrophobic_regions(sequence: str, *, window: int = 19) -> list[dict]:
    regions = []
    for start in range(max(0, len(sequence) - window + 1)):
        peptide = sequence[start : start + window]
        mean = sum(HYDROPATHY[item] for item in peptide) / window
        if mean >= 1.6:
            regions.append(
                {
                    "start": start + 1,
                    "end": start + window,
                    "meanHydropathy": round(mean, 3),
                }
            )
    return merge_regions(regions, "meanHydropathy")


def find_low_complexity_regions(sequence: str, *, window: int = 12) -> list[dict]:
    regions = []
    for start in range(max(0, len(sequence) - window + 1)):
        peptide = sequence[start : start + window]
        entropy = shannon_entropy(peptide)
        if entropy < 2.2:
            regions.append(
                {
                    "start": start + 1,
                    "end": start + window,
                    "entropy": round(entropy, 3),
                }
            )
    return merge_regions(regions, "entropy")


def merge_regions(regions: list[dict], metric: str) -> list[dict]:
    merged = []
    for region in regions:
        if merged and region["start"] <= merged[-1]["end"] + 1:
            merged[-1]["end"] = max(merged[-1]["end"], region["end"])
            if metric == "entropy":
                merged[-1][metric] = min(merged[-1][metric], region[metric])
            else:
                merged[-1][metric] = max(merged[-1][metric], region[metric])
        else:
            merged.append(dict(region))
    return merged


def shannon_entropy(sequence: str) -> float:
    counts = Counter(sequence)
    length = len(sequence)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def candidate_id(source: str, allele: str, start: int, sequence: str) -> str:
    digest = hashlib.sha256(f"{source}|{allele}|{start}|{sequence}".encode()).hexdigest()
    return digest[:16]


def wrap_sequence(sequence: str, width: int = 70) -> str:
    return "\n".join(sequence[index : index + width] for index in range(0, len(sequence), width))
