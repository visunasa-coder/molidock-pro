from fastapi import APIRouter
from pydantic import BaseModel

from app.services.toxicity import predict_toxicity

router = APIRouter(
    prefix="/toxicity",
    tags=["Toxicity"]
)


class ToxicityRequest(BaseModel):
    smiles: str


@router.post("/predict")
def toxicity_predict(request: ToxicityRequest):
    return predict_toxicity(request.smiles)