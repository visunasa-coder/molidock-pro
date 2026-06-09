import pytest

from app.services.iedb import (
    IEDBPredictionError,
    parse_bcell_tsv,
    parse_mhc_tsv,
    parse_processing_tsv,
    predict_mhc_binding,
)


MHC_I_TSV = """allele\tseq_num\tstart\tend\tlength\tpeptide\tcore\ticore\tscore\tpercentile_rank
HLA-A*01:01\t1\t2\t10\t9\tLYNTVATLY\tLYNTVATLY\tLYNTVATLY\t0.0909\t1.1
HLA-A*01:01\t1\t1\t9\t9\tSLYNTVATL\tSLYNTVATL\tSLYNTVATL\t0.00218\t9.1
"""

MHC_II_BA_TSV = """allele\tseq_num\tstart\tend\tlength\tcore_peptide\tpeptide\tic50\trank
HLA-DRB1*01:01\t1\t1\t15\t15\tYNTVATLYC\tSLYNTVATLYCVHQR\t138.37\t3.0
"""

BCELL_TSV = """Position\tResidue\tScore\tAssignment
0\tA\t0.2\t.
1\tC\t0.6\tE
2\tD\t0.7\tE
3\tE\t0.4\t.
4\tF\t0.8\tE
"""

PROCESSING_TSV = """allele\tseq_num\tstart\tend\tlength\tpeptide\tproteasome_score\ttap_score\tmhc_score\tprocessing_score\ttotal_score\tic50_score
HLA-A*01:01\t1\t2\t10\t9\tLYNTVATLY\t1.2896\t1.3692\t-3.8196\t2.6588\t-1.1608\t6600.4
"""


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def post(self, url: str, *, data: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "data": data, "timeout": timeout})
        return FakeResponse(self.text)


def test_parse_mhc_i_tsv_marks_rank_binders() -> None:
    rows = parse_mhc_tsv(MHC_I_TSV, mhc_class="mhc-i", rank_threshold=2.0)

    assert rows[0]["peptide"] == "LYNTVATLY"
    assert rows[0]["score"] == 0.0909
    assert rows[0]["affinityNm"] is None
    assert rows[0]["isBinder"] is True
    assert rows[1]["isBinder"] is False


def test_parse_mhc_ii_binding_affinity_tsv() -> None:
    rows = parse_mhc_tsv(MHC_II_BA_TSV, mhc_class="mhc-ii", rank_threshold=10.0)

    assert rows[0]["core"] == "YNTVATLYC"
    assert rows[0]["affinityNm"] == 138.37
    assert rows[0]["rankPercent"] == 3.0


def test_predict_mhc_i_repeats_length_for_each_allele() -> None:
    client = FakeClient(MHC_I_TSV)

    result = predict_mhc_binding(
        sequence="SLYNTVATLYCVHQRIDV",
        mhc_class="mhc-i",
        alleles=["HLA-A*01:01", "HLA-A*02:01"],
        peptide_length=9,
        method="recommended_epitope",
        rank_threshold=2.0,
        result_limit=1,
        http_client=client,
    )

    assert client.calls[0]["data"]["length"] == "9,9"
    assert client.calls[0]["url"].endswith("/mhci/")
    assert result["binderCount"] == 1
    assert result["totalPredictions"] == 2
    assert result["returnedPredictions"] == 1


def test_parse_bcell_tsv_builds_contiguous_regions() -> None:
    residues, regions = parse_bcell_tsv(BCELL_TSV)

    assert residues[0]["position"] == 1
    assert regions == [
        {
            "start": 2,
            "end": 3,
            "length": 2,
            "sequence": "CD",
            "meanScore": 0.65,
            "maxScore": 0.7,
        },
        {
            "start": 5,
            "end": 5,
            "length": 1,
            "sequence": "F",
            "meanScore": 0.8,
            "maxScore": 0.8,
        },
    ]


def test_parse_processing_tsv_normalizes_scores() -> None:
    rows = parse_processing_tsv(PROCESSING_TSV)

    assert rows[0]["peptide"] == "LYNTVATLY"
    assert rows[0]["processingScore"] == 2.6588
    assert rows[0]["totalScore"] == -1.1608
    assert rows[0]["affinityNm"] == 6600.4


def test_parse_mhc_tsv_rejects_provider_contract_change() -> None:
    with pytest.raises(IEDBPredictionError, match="missing expected columns"):
        parse_mhc_tsv(
            "allele\tpeptide\nHLA-A*01:01\tSLYNTVATL",
            mhc_class="mhc-i",
            rank_threshold=1.0,
        )
