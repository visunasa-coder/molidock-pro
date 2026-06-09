from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import User
from app.routers import vaccine
from app.schemas import (
    VaccineAnalysisRequest,
    VaccineConstructRequest,
    VaccineProjectCreate,
)


SEQUENCE = "SLYNTVATLYCVHQRIDVACDEFGHIKLMNPQRSTVWY"


def persist_without_files(project, db: Session) -> None:
    db.add(project)
    db.commit()
    db.refresh(project)


def test_project_analysis_and_construct_flow(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            email="scientist@example.com",
            full_name="Scientist",
            password_hash="hashed",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        monkeypatch.setattr(vaccine, "persist_vaccine_artifacts", persist_without_files)
        created = vaccine.create_vaccine_project(
            VaccineProjectCreate(name="Test vaccine", fasta=SEQUENCE),
            db=db,
            user=user,
        )
        assert created["status"] == "profiled"
        assert created["results"]["sequenceProfile"]["length"] == len(SEQUENCE)

        def fake_mhc(**kwargs):
            peptide = kwargs["sequence"][: kwargs["peptide_length"]]
            return {
                "results": [
                    {
                        "allele": kwargs["alleles"][0],
                        "start": 1,
                        "end": len(peptide),
                        "length": len(peptide),
                        "peptide": peptide,
                        "core": peptide,
                        "rankPercent": 0.5,
                        "isBinder": True,
                    }
                ],
                "totalPredictions": 1,
            }

        monkeypatch.setattr(vaccine, "predict_mhc_binding", fake_mhc)
        monkeypatch.setattr(
            vaccine,
            "predict_bcell_epitopes",
            lambda **kwargs: {
                "regions": [
                    {
                        "start": 1,
                        "end": 8,
                        "length": 8,
                        "sequence": kwargs["sequence"][:8],
                        "meanScore": 0.7,
                        "maxScore": 0.8,
                    }
                ],
                "regionCount": 1,
            },
        )
        monkeypatch.setattr(
            vaccine,
            "predict_mhci_processing",
            lambda **kwargs: {
                "results": [
                    {
                        "allele": kwargs["alleles"][0],
                        "start": 1,
                        "peptide": kwargs["sequence"][: kwargs["peptide_length"]],
                        "totalScore": 1.0,
                    }
                ]
            },
        )

        analyzed = vaccine.analyze_vaccine_project(
            created["id"],
            VaccineAnalysisRequest(),
            db=db,
            user=user,
        )
        assert analyzed["status"] == "analyzed"
        assert analyzed["results"]["candidates"]
        candidate_id = analyzed["results"]["candidates"][0]["id"]

        constructed = vaccine.build_vaccine_construct(
            created["id"],
            VaccineConstructRequest(candidate_ids=[candidate_id]),
            db=db,
            user=user,
        )
        assert constructed["status"] == "construct_ready"
        assert constructed["results"]["construct"]["epitopeCount"] == 1
