import pytest

from app.services.vaccine_design import (
    assemble_construct,
    estimate_isoelectric_point,
    profile_sequence,
    rank_epitope_candidates,
)


def test_profile_sequence_returns_physicochemical_values_and_flags() -> None:
    profile = profile_sequence("M" + "LIVVVA" * 5 + "DEKR")

    assert profile["length"] == 35
    assert profile["molecularWeightDa"] > 3000
    assert 0 <= profile["estimatedPI"] <= 14
    assert profile["hydrophobicRegions"]
    assert "methodNote" in profile


def test_estimated_pi_separates_acidic_and_basic_sequences() -> None:
    assert estimate_isoelectric_point("DDDEEE") < 5
    assert estimate_isoelectric_point("KKKRRR") > 9


def test_rank_and_assemble_construct() -> None:
    mhc_i = {
        "results": [
            {
                "allele": "HLA-A*02:01",
                "start": 2,
                "end": 10,
                "length": 9,
                "peptide": "LYNTVATLY",
                "core": "LYNTVATLY",
                "rankPercent": 0.4,
                "isBinder": True,
            }
        ]
    }
    mhc_ii = {"results": []}
    bcell = {
        "regions": [
            {
                "start": 4,
                "end": 11,
                "length": 8,
                "sequence": "NTVATLYC",
                "meanScore": 0.7,
                "maxScore": 0.8,
            }
        ]
    }
    processing = {
        "results": [
            {
                "allele": "HLA-A*02:01",
                "start": 2,
                "peptide": "LYNTVATLY",
                "totalScore": 1.5,
            }
        ]
    }

    candidates = rank_epitope_candidates(
        mhc_i=mhc_i,
        mhc_ii=mhc_ii,
        bcell=bcell,
        processing=processing,
    )
    assert candidates[0]["type"] == "mhc-i"
    assert candidates[0]["bcellOverlap"] > 0
    assert candidates[0]["processingScore"] == 1.5

    construct = assemble_construct(
        candidates,
        [candidates[0]["id"], candidates[1]["id"]],
    )
    assert construct["proteinSequence"].startswith("M")
    assert construct["epitopeCount"] == 2
    assert construct["dnaSequence"].endswith("TAA")
    assert 0 < construct["gcPercent"] <= 100


def test_assemble_construct_rejects_unknown_candidates() -> None:
    with pytest.raises(ValueError, match="Select at least one"):
        assemble_construct([], ["missing"])
