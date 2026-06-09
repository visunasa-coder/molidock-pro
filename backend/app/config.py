from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "MoliDock Pro API"
    environment: str = "development"
    api_base_url: str = "http://127.0.0.1:8000"
    frontend_base_url: str = "http://127.0.0.1:5173"

    database_url: str = "sqlite:///./molidock.db"
    storage_dir: Path = Path("storage")
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    secret_key: str = Field(
        default="change-this-before-production",
        min_length=24,
        description="JWT signing key. Replace in production.",
    )
    access_token_expire_minutes: int = 60 * 24

    max_upload_mb: int = 75
    max_parallel_cpu: int = 4
    job_timeout_seconds: int = 60 * 60 * 3

    vina_binary: str = "vina"
    obabel_binary: str = "obabel"
    prepare_receptor_binary: str = ""
    allow_demo_docking: bool = False

    iedb_tools_base_url: str = "https://tools-cluster-interface.iedb.org/tools_api"
    iedb_timeout_seconds: int = 90
    iedb_max_predictions: int = 20_000
    iedb_result_limit: int = 500
    vaccine_max_sequence_aa: int = 5_000

    ncbi_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ncbi_blast_url: str = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
    ncbi_tool: str = "MoliDockPro"
    ncbi_email: str = ""
    ncbi_api_key: str = ""
    ncbi_timeout_seconds: int = 60

    free_monthly_jobs: int = 5
    pro_monthly_jobs: int = 100
    lab_monthly_jobs: int = 1000

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_lab_price_id: str = ""

    @field_validator("storage_dir", mode="before")
    @classmethod
    def normalize_storage_dir(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def upload_limit_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "jobs").mkdir(parents=True, exist_ok=True)
    return settings
