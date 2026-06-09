from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import admet, auth, auto, billing, docking, health, protein, pubchem, vaccine
settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(docking.router)
app.include_router(admet.router)
app.include_router(billing.router)
app.include_router(pubchem.router)
app.include_router(protein.router)
app.include_router(auto.router)
app.include_router(vaccine.router)

@app.on_event("startup")
def startup() -> None:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
