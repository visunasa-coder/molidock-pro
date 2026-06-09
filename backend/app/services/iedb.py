import csv
import io
from typing import Any

import requests

from app.config import get_settings


IEDB_PROVIDER_NAME = "IEDB Analysis Resource"
IEDB_PROVIDER_URL = "https://tools.iedb.org/main/tools-api/"


class IEDBPredictionError(RuntimeError):
    pass


def predict_mhc_binding(
    *,
    sequence: str,
    mhc_class: str,
    alleles: list[str],
    peptide_length: int,
    method: str,
    rank_threshold: float,
    result_limit: int,
    http_client: Any | None = None,
) -> dict:
    settings = get_settings()
    endpoint = "mhci" if mhc_class == "mhc-i" else "mhcii"
    payload = {
        "method": method,
        "sequence_text": sequence,
        "allele": ",".join(alleles),
        "length": (
            ",".join([str(peptide_length)] * len(alleles))
            if mhc_class == "mhc-i"
            else str(peptide_length)
        ),
    }
    text = _post_tsv(
        endpoint,
        payload,
        http_client=http_client,
        base_url=settings.iedb_tools_base_url,
        timeout_seconds=settings.iedb_timeout_seconds,
    )
    predictions = parse_mhc_tsv(
        text,
        mhc_class=mhc_class,
        rank_threshold=rank_threshold,
    )
    predictions.sort(key=lambda item: (item["rankPercent"], item["allele"], item["start"]))

    return {
        "provider": IEDB_PROVIDER_NAME,
        "providerUrl": IEDB_PROVIDER_URL,
        "predictor": mhc_class,
        "method": method,
        "alleles": alleles,
        "peptideLength": peptide_length,
        "rankThreshold": rank_threshold,
        "totalPredictions": len(predictions),
        "binderCount": sum(item["isBinder"] for item in predictions),
        "returnedPredictions": min(len(predictions), result_limit),
        "results": predictions[:result_limit],
        "scientificNote": (
            "Percentile rank is a prioritization metric, not experimental evidence of "
            "immunogenicity or protection."
        ),
    }


def predict_bcell_epitopes(
    *,
    sequence: str,
    method: str,
    http_client: Any | None = None,
) -> dict:
    settings = get_settings()
    text = _post_tsv(
        "bcell",
        {"method": method, "sequence_text": sequence},
        http_client=http_client,
        base_url=settings.iedb_tools_base_url,
        timeout_seconds=settings.iedb_timeout_seconds,
    )
    residues, regions = parse_bcell_tsv(text)

    return {
        "provider": IEDB_PROVIDER_NAME,
        "providerUrl": IEDB_PROVIDER_URL,
        "predictor": "b-cell",
        "method": method,
        "sequenceLength": len(residues),
        "epitopeResidueCount": sum(item["isEpitope"] for item in residues),
        "regionCount": len(regions),
        "regions": regions,
        "residues": residues,
        "scientificNote": (
            "Predicted linear B-cell regions require structural, accessibility, and "
            "experimental validation."
        ),
    }


def predict_mhci_processing(
    *,
    sequence: str,
    alleles: list[str],
    peptide_length: int,
    result_limit: int,
    http_client: Any | None = None,
) -> dict:
    settings = get_settings()
    text = _post_tsv(
        "processing",
        {
            "method": "recommended",
            "sequence_text": sequence,
            "allele": ",".join(alleles),
            "length": ",".join([str(peptide_length)] * len(alleles)),
        },
        http_client=http_client,
        base_url=settings.iedb_tools_base_url,
        timeout_seconds=settings.iedb_timeout_seconds,
    )
    predictions = parse_processing_tsv(text)
    predictions.sort(key=lambda item: (-item["totalScore"], item["allele"], item["start"]))
    return {
        "provider": IEDB_PROVIDER_NAME,
        "providerUrl": IEDB_PROVIDER_URL,
        "predictor": "mhc-i-processing",
        "method": "recommended",
        "alleles": alleles,
        "peptideLength": peptide_length,
        "totalPredictions": len(predictions),
        "returnedPredictions": min(len(predictions), result_limit),
        "results": predictions[:result_limit],
        "scientificNote": (
            "Processing scores combine modeled proteasomal cleavage, TAP transport, and "
            "MHC binding; they are not experimental presentation measurements."
        ),
    }


def parse_mhc_tsv(text: str, *, mhc_class: str, rank_threshold: float) -> list[dict]:
    rows = _read_tsv(text)
    rank_column = "percentile_rank" if mhc_class == "mhc-i" else "rank"
    required = {"allele", "start", "end", "length", "peptide", rank_column}
    _require_columns(rows, required)

    predictions = []
    for row in rows:
        rank = _required_float(row, rank_column)
        predictions.append(
            {
                "allele": row["allele"],
                "sequenceNumber": _required_int(row, "seq_num"),
                "start": _required_int(row, "start"),
                "end": _required_int(row, "end"),
                "length": _required_int(row, "length"),
                "peptide": row["peptide"],
                "core": row.get("core") or row.get("core_peptide") or row["peptide"],
                "score": _optional_float(row.get("score")),
                "affinityNm": _optional_float(row.get("ic50")),
                "rankPercent": rank,
                "isBinder": rank <= rank_threshold,
            }
        )
    return predictions


def parse_processing_tsv(text: str) -> list[dict]:
    rows = _read_tsv(text)
    _require_columns(
        rows,
        {
            "allele",
            "seq_num",
            "start",
            "end",
            "length",
            "peptide",
            "proteasome_score",
            "tap_score",
            "mhc_score",
            "processing_score",
            "total_score",
            "ic50_score",
        },
    )
    return [
        {
            "allele": row["allele"],
            "sequenceNumber": _required_int(row, "seq_num"),
            "start": _required_int(row, "start"),
            "end": _required_int(row, "end"),
            "length": _required_int(row, "length"),
            "peptide": row["peptide"],
            "proteasomeScore": _required_float(row, "proteasome_score"),
            "tapScore": _required_float(row, "tap_score"),
            "mhcScore": _required_float(row, "mhc_score"),
            "processingScore": _required_float(row, "processing_score"),
            "totalScore": _required_float(row, "total_score"),
            "affinityNm": _required_float(row, "ic50_score"),
        }
        for row in rows
    ]


def parse_bcell_tsv(text: str) -> tuple[list[dict], list[dict]]:
    rows = _read_tsv(text)
    _require_columns(rows, {"Position", "Residue", "Score", "Assignment"})

    residues = []
    for row in rows:
        residues.append(
            {
                "position": _required_int(row, "Position") + 1,
                "residue": row["Residue"],
                "score": _required_float(row, "Score"),
                "isEpitope": row["Assignment"].strip().upper() == "E",
            }
        )

    regions = []
    active: list[dict] = []
    for residue in residues:
        if residue["isEpitope"]:
            active.append(residue)
            continue
        if active:
            regions.append(_build_bcell_region(active))
            active = []
    if active:
        regions.append(_build_bcell_region(active))

    return residues, regions


def _post_tsv(
    endpoint: str,
    payload: dict[str, str],
    *,
    http_client: Any | None,
    base_url: str,
    timeout_seconds: int,
) -> str:
    client = http_client or requests
    url = f"{base_url.rstrip('/')}/{endpoint}/"
    try:
        response = client.post(url, data=payload, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IEDBPredictionError(f"IEDB {endpoint} request failed: {exc}") from exc

    text = response.text.strip()
    if not text:
        raise IEDBPredictionError(f"IEDB {endpoint} returned an empty response.")
    if "\t" not in text.partition("\n")[0]:
        detail = " ".join(text.split())[:240]
        raise IEDBPredictionError(f"IEDB {endpoint} returned an unexpected response: {detail}")
    return text


def _read_tsv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.strip()), delimiter="\t")
    rows = list(reader)
    if not reader.fieldnames or not rows:
        raise IEDBPredictionError("IEDB returned no prediction rows.")
    return rows


def _require_columns(rows: list[dict[str, str]], required: set[str]) -> None:
    columns = set(rows[0])
    missing = sorted(required - columns)
    if missing:
        raise IEDBPredictionError(
            f"IEDB response is missing expected columns: {', '.join(missing)}"
        )


def _required_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise IEDBPredictionError(f"IEDB returned an invalid {key} value.") from exc


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise IEDBPredictionError("IEDB returned an invalid numeric prediction value.") from exc


def _required_int(row: dict[str, str], key: str) -> int:
    try:
        return int(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise IEDBPredictionError(f"IEDB returned an invalid {key} value.") from exc


def _build_bcell_region(residues: list[dict]) -> dict:
    scores = [item["score"] for item in residues]
    return {
        "start": residues[0]["position"],
        "end": residues[-1]["position"],
        "length": len(residues),
        "sequence": "".join(item["residue"] for item in residues),
        "meanScore": round(sum(scores) / len(scores), 4),
        "maxScore": max(scores),
    }
