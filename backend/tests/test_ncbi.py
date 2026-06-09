from app.services.ncbi import parse_blast_xml, submit_blastp


BLAST_XML = """<?xml version="1.0"?>
<BlastOutput>
  <BlastOutput_iterations>
    <Iteration>
      <Iteration_hits>
        <Hit>
          <Hit_def>Example protein [Example organism]</Hit_def>
          <Hit_accession>XP_123</Hit_accession>
          <Hit_len>200</Hit_len>
          <Hit_hsps>
            <Hsp>
              <Hsp_bit-score>80.5</Hsp_bit-score>
              <Hsp_evalue>1e-20</Hsp_evalue>
              <Hsp_query-from>1</Hsp_query-from>
              <Hsp_query-to>50</Hsp_query-to>
              <Hsp_hit-from>10</Hsp_hit-from>
              <Hsp_hit-to>59</Hsp_hit-to>
              <Hsp_identity>40</Hsp_identity>
              <Hsp_positive>45</Hsp_positive>
              <Hsp_gaps>2</Hsp_gaps>
              <Hsp_align-len>50</Hsp_align-len>
            </Hsp>
          </Hit_hsps>
        </Hit>
      </Iteration_hits>
    </Iteration>
  </BlastOutput_iterations>
</BlastOutput>
"""


class FakeResponse:
    text = "RID = TEST123\nRTOE = 12\n"

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self):
        self.payload = None

    def post(self, url: str, *, data: dict, timeout: int) -> FakeResponse:
        self.payload = data
        return FakeResponse()


def test_parse_blast_xml_normalizes_best_hsp() -> None:
    hits = parse_blast_xml(BLAST_XML)

    assert hits[0]["accession"] == "XP_123"
    assert hits[0]["identityPercent"] == 80.0
    assert hits[0]["positivePercent"] == 90.0
    assert hits[0]["gapPercent"] == 4.0


def test_submit_blastp_extracts_rid_and_uses_blastp() -> None:
    client = FakeClient()
    result = submit_blastp(
        "SLYNTVATLYCVHQRIDV",
        database="swissprot",
        http_client=client,
    )

    assert result["rid"] == "TEST123"
    assert result["estimatedSeconds"] == 12
    assert client.payload["PROGRAM"] == "blastp"
    assert client.payload["DATABASE"] == "swissprot"
