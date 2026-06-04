from fastapi import APIRouter, Depends, Form, HTTPException
import requests

from app.deps import get_current_user
from app.models import User
from app.schemas import ADMETPrediction
from app.services.admet import predict_admet


router = APIRouter(prefix="/admet", tags=["admet"])


@router.post("", response_model=ADMETPrediction)
def admet(
    smiles: str = Form(...),
    user: User = Depends(get_current_user),
) -> ADMETPrediction:
    return predict_admet(smiles.strip())


@router.get("/compound", response_model=ADMETPrediction)
def admet_by_compound_name(name: str):
    try:
        cid_url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            f"{name}/cids/JSON"
        )

        cid_response = requests.get(cid_url, timeout=20)
        cid_response.raise_for_status()

        cid = cid_response.json()["IdentifierList"]["CID"][0]

        prop_url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
            f"{cid}/property/CanonicalSMILES/JSON"
        )

        prop_response = requests.get(prop_url, timeout=20)
        prop_response.raise_for_status()

        props = prop_response.json()["PropertyTable"]["Properties"][0]
 
        smiles = (
             props.get("CanonicalSMILES")
            or props.get("SMILES")
            or props.get("ConnectivitySMILES")
            or props.get("IsomericSMILES")
        )

        if not smiles:
            raise HTTPException(status_code=404, detail=f"No SMILES found. PubChem returned: {props}")

        return predict_admet(smiles.strip())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))