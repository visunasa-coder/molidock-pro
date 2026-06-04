from fastapi import APIRouter

router = APIRouter(prefix="/compound", tags=["Compound Search"])


@router.get("/search")
def search_compound(name: str):
    return {
        "query": name,
        "message": "PubChem search route is working"
    }