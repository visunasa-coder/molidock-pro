import pytest
from fastapi import HTTPException

from app.routers.vaccine import (
    clean_protein_sequence,
    parse_hla_alleles,
    plan_vaccine_construct,
)


def test_clean_protein_sequence_removes_fasta_header():
    assert clean_protein_sequence(">antigen\nACD EFG\nHIK") == "ACDEFGHIK"


def test_plan_vaccine_construct_returns_windows_and_gates():
    result = plan_vaccine_construct(
        project_name="Spike candidate",
        construct_type="mhc-i",
        fasta=">spike\nACDEFGHIKLMNPQRSTVWYACDEFGHIK",
        user=object(),
    )

    assert result["projectName"] == "Spike candidate"
    assert result["constructType"] == "mhc-i"
    assert result["length"] == 29
    assert result["windows"][0]["sequence"] == "ACDEFGHIK"
    assert "Sequence QC" in result["requiredGates"]


def test_parse_hla_alleles_deduplicates_human_alleles():
    assert parse_hla_alleles(
        "HLA-A*02:01, HLA-A*01:01\nHLA-A*02:01",
        mhc_class="mhc-i",
    ) == ["HLA-A*02:01", "HLA-A*01:01"]


def test_parse_hla_alleles_rejects_invalid_format():
    with pytest.raises(HTTPException, match="Invalid human HLA allele format"):
        parse_hla_alleles("A2", mhc_class="mhc-i")
