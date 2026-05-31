from fastapi import APIRouter, Depends, Form

from app.deps import get_current_user
from app.models import User
from app.schemas import ADMETPrediction
from app.services.admet import predict_admet


router = APIRouter(prefix="/admet", tags=["admet"])


@router.post("", response_model=ADMETPrediction)
def admet(smiles: str = Form(...), user: User = Depends(get_current_user)) -> ADMETPrediction:
    return predict_admet(smiles.strip())

