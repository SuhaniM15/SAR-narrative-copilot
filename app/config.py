from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SAR Narrative Copilot"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"
    database_url: str = f"sqlite:///{(DATA_DIR / 'sar_copilot.db').as_posix()}"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    environment: str = "development"
    knowledge_dir: str = str(DATA_DIR / "knowledge")
    chroma_dir: str = str(DATA_DIR / "chroma")
    rag_top_k: int = 3
    chroma_collection: str = "sar_policy_knowledge"


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
