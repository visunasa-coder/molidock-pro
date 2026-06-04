from app.services.converter import sdf_to_pdbqt
from fastapi import APIRouter, HTTPException
import requests

router = APIRouter(prefix="/compound", tags=["Compound Search"])


@router.get("/search")
def search_compound(name: str):
    # Step 1: Get CID from compound name
    cid_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{name}/cids/JSON"
    )

    cid_response = requests.get(cid_url, timeout=15)

    if cid_response.status_code != 200:
        raise HTTPException(status_code=404, detail="Compound not found in PubChem")

    cid_data = cid_response.json()
    cids = cid_data.get("IdentifierList", {}).get("CID", [])

    if not cids:
        raise HTTPException(status_code=404, detail="No CID found")

    cid = cids[0]

    # Step 2: Get compound properties
    prop_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
        f"{cid}/property/"
        "MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName/JSON"
    )

    prop_response = requests.get(prop_url, timeout=15)

    if prop_response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch compound properties")

    props = prop_response.json()["PropertyTable"]["Properties"][0]

    return {
        "query": name,
        "cid": cid,
        "iupac_name": props.get("IUPACName"),
        "molecular_formula": props.get("MolecularFormula"),
        "molecular_weight": props.get("MolecularWeight"),
        "canonical_smiles": props.get("CanonicalSMILES"),
    }

@router.get("/download-sdf/{cid}")
def download_sdf(cid: int):
    sdf_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
        f"{cid}/SDF?record_type=3d"
    )

    response = requests.get(sdf_url, timeout=30)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="3D SDF not available for this compound")

    file_path = f"storage/compound_{cid}.sdf"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    return {
        "cid": cid,
        "message": "SDF downloaded successfully",
        "file_path": file_path
    }

@router.get("/convert-pdbqt/{cid}")
def convert_compound_to_pdbqt(cid: int):
    sdf_path = f"storage/compound_{cid}.sdf"

    try:
        pdbqt_path = sdf_to_pdbqt(sdf_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "cid": cid,
        "message": "PDBQT converted successfully",
        "pdbqt_path": pdbqt_path
    }