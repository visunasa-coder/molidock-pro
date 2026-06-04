from app.services.grid import predict_grid_from_pdb
from app.services.converter import pdb_to_pdbqt
from fastapi import APIRouter, HTTPException
import requests

router = APIRouter(prefix="/protein", tags=["Protein Search"])


@router.get("/search")
def search_protein(name: str):
    query = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {
                "value": name
            }
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {
                "start": 0,
                "rows": 10
            }
        }
    }

    response = requests.post(
        "https://search.rcsb.org/rcsbsearch/v2/query",
        json=query,
        timeout=20
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"PDB search failed: {response.text}"
        )

    return response.json()


@router.get("/download/{pdb_id}")
def download_pdb(pdb_id: str):
    pdb_id = pdb_id.upper()

    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    response = requests.get(url, timeout=30)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="PDB file not found")

    file_path = f"storage/{pdb_id}.pdb"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    return {
        "pdb_id": pdb_id,
        "message": "PDB downloaded successfully",
        "file_path": file_path
    }

@router.get("/prepare/{pdb_id}")
def prepare_protein(pdb_id: str):
    pdb_id = pdb_id.upper()
    pdb_path = f"storage/{pdb_id}.pdb"

    try:
        pdbqt_path = pdb_to_pdbqt(pdb_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "pdb_id": pdb_id,
        "message": "Protein prepared successfully",
        "pdbqt_path": pdbqt_path
    }

@router.get("/grid/{pdb_id}")
def predict_grid(pdb_id: str):
    pdb_id = pdb_id.upper()
    pdb_path = f"storage/{pdb_id}.pdb"

    try:
        grid = predict_grid_from_pdb(pdb_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "pdb_id": pdb_id,
        "message": "Grid predicted successfully",
        "grid": grid
    }