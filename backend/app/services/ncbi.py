import re
import xml.etree.ElementTree as ET
from typing import Any

import requests

from app.config import get_settings


RID_PATTERN = re.compile(r"RID\s*=\s*([A-Z0-9-]+)")
RTOE_PATTERN = re.compile(r"RTOE\s*=\s*(\d+)")


class NCBIServiceError(RuntimeError):
    pass


def search_proteins(query: str, *, limit: int = 10, http_client: Any | None = None) -> list[dict]:
    settings = get_settings()
    client = http_client or requests
    common = _common_params()

    try:
        search_response = client.get(
            f"{settings.ncbi_base_url.rstrip('/')}/esearch.fcgi",
            params={
                **common,
                "db": "protein",
                "term": query,
                "retmode": "json",
                "retmax": limit,
            },
            timeout=settings.ncbi_timeout_seconds,
        )
        search_response.raise_for_status()
        identifiers = search_response.json().get("esearchresult", {}).get("idlist", [])
        if not identifiers:
            return []

        summary_response = client.get(
            f"{settings.ncbi_base_url.rstrip('/')}/esummary.fcgi",
            params={
                **common,
                "db": "protein",
                "id": ",".join(identifiers),
                "retmode": "json",
            },
            timeout=settings.ncbi_timeout_seconds,
        )
        summary_response.raise_for_status()
        payload = summary_response.json().get("result", {})
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise NCBIServiceError(f"NCBI protein search failed: {exc}") from exc

    results = []
    for identifier in identifiers:
        item = payload.get(identifier, {})
        results.append(
            {
                "uid": identifier,
                "accession": item.get("caption", ""),
                "title": item.get("title", ""),
                "organism": item.get("organism", ""),
                "length": item.get("slen"),
                "updated": item.get("updatedate", ""),
            }
        )
    return results


def fetch_protein_fasta(accession: str, *, http_client: Any | None = None) -> dict:
    settings = get_settings()
    client = http_client or requests
    try:
        response = client.get(
            f"{settings.ncbi_base_url.rstrip('/')}/efetch.fcgi",
            params={
                **_common_params(),
                "db": "protein",
                "id": accession,
                "rettype": "fasta",
                "retmode": "text",
            },
            timeout=settings.ncbi_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NCBIServiceError(f"NCBI protein fetch failed: {exc}") from exc

    fasta = response.text.strip()
    if not fasta.startswith(">"):
        raise NCBIServiceError("NCBI did not return a protein FASTA record.")
    header, *sequence_lines = fasta.splitlines()
    return {
        "accession": accession,
        "header": header[1:].strip(),
        "fasta": fasta,
        "sequence": "".join(sequence_lines).replace(" ", "").upper(),
        "provider": "NCBI Protein",
        "providerUrl": f"https://www.ncbi.nlm.nih.gov/protein/{accession}",
    }


def submit_blastp(
    sequence: str,
    *,
    database: str = "swissprot",
    hitlist_size: int = 20,
    http_client: Any | None = None,
) -> dict:
    settings = get_settings()
    client = http_client or requests
    payload = {
        "CMD": "Put",
        "PROGRAM": "blastp",
        "DATABASE": database,
        "QUERY": sequence,
        "HITLIST_SIZE": hitlist_size,
        "FORMAT_TYPE": "XML2",
        "TOOL": settings.ncbi_tool,
    }
    if settings.ncbi_email:
        payload["EMAIL"] = settings.ncbi_email

    try:
        response = client.post(
            settings.ncbi_blast_url,
            data=payload,
            timeout=settings.ncbi_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NCBIServiceError(f"NCBI BLAST submission failed: {exc}") from exc

    rid_match = RID_PATTERN.search(response.text)
    rtoe_match = RTOE_PATTERN.search(response.text)
    if not rid_match:
        detail = " ".join(response.text.split())[:240]
        raise NCBIServiceError(f"NCBI BLAST did not return a request ID: {detail}")
    return {
        "rid": rid_match.group(1),
        "estimatedSeconds": int(rtoe_match.group(1)) if rtoe_match else None,
        "database": database,
        "provider": "NCBI BLAST",
        "providerUrl": "https://blast.ncbi.nlm.nih.gov/",
        "pollAfterSeconds": 60,
    }


def get_blastp_result(rid: str, *, http_client: Any | None = None) -> dict:
    settings = get_settings()
    client = http_client or requests
    try:
        status_response = client.get(
            settings.ncbi_blast_url,
            params={"CMD": "Get", "RID": rid, "FORMAT_OBJECT": "SearchInfo"},
            timeout=settings.ncbi_timeout_seconds,
        )
        status_response.raise_for_status()
    except requests.RequestException as exc:
        raise NCBIServiceError(f"NCBI BLAST status check failed: {exc}") from exc

    text = status_response.text
    if "Status=WAITING" in text:
        return {"rid": rid, "status": "waiting", "hits": []}
    if "Status=FAILED" in text:
        return {"rid": rid, "status": "failed", "hits": []}
    if "Status=UNKNOWN" in text:
        return {"rid": rid, "status": "expired", "hits": []}
    if "ThereAreHits=no" in text:
        return {"rid": rid, "status": "completed", "hits": []}

    try:
        result_response = client.get(
            settings.ncbi_blast_url,
            params={"CMD": "Get", "RID": rid, "FORMAT_TYPE": "XML"},
            timeout=settings.ncbi_timeout_seconds,
        )
        result_response.raise_for_status()
        hits = parse_blast_xml(result_response.text)
    except (requests.RequestException, ET.ParseError) as exc:
        raise NCBIServiceError(f"NCBI BLAST result retrieval failed: {exc}") from exc
    return {"rid": rid, "status": "completed", "hits": hits}


def parse_blast_xml(text: str) -> list[dict]:
    root = ET.fromstring(text)
    hits = []
    for hit in root.findall(".//Hit"):
        best_hsp = hit.find("./Hit_hsps/Hsp")
        if best_hsp is None:
            continue
        align_length = _xml_int(best_hsp, "Hsp_align-len")
        identities = _xml_int(best_hsp, "Hsp_identity")
        positives = _xml_int(best_hsp, "Hsp_positive")
        gaps = _xml_int(best_hsp, "Hsp_gaps")
        hits.append(
            {
                "accession": _xml_text(hit, "Hit_accession"),
                "title": _xml_text(hit, "Hit_def"),
                "length": _xml_int(hit, "Hit_len"),
                "evalue": float(_xml_text(best_hsp, "Hsp_evalue") or 0),
                "bitScore": float(_xml_text(best_hsp, "Hsp_bit-score") or 0),
                "identityPercent": round((identities / align_length) * 100, 2)
                if align_length
                else 0,
                "positivePercent": round((positives / align_length) * 100, 2)
                if align_length
                else 0,
                "gapPercent": round((gaps / align_length) * 100, 2) if align_length else 0,
                "alignmentLength": align_length,
                "queryStart": _xml_int(best_hsp, "Hsp_query-from"),
                "queryEnd": _xml_int(best_hsp, "Hsp_query-to"),
                "subjectStart": _xml_int(best_hsp, "Hsp_hit-from"),
                "subjectEnd": _xml_int(best_hsp, "Hsp_hit-to"),
            }
        )
    return hits


def _common_params() -> dict[str, str]:
    settings = get_settings()
    params = {"tool": settings.ncbi_tool}
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


def _xml_text(element: ET.Element, path: str) -> str:
    value = element.findtext(path)
    return value.strip() if value else ""


def _xml_int(element: ET.Element, path: str) -> int:
    value = _xml_text(element, path)
    return int(value) if value else 0
