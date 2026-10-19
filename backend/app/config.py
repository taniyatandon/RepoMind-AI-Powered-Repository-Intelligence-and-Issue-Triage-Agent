import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./repomind.db"
    JWT_SECRET_KEY: str = Field(default_factory=secrets.token_urlsafe)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GITHUB_TOKEN: str | None = None
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Phase 2 — Semantic Code Search & AI Intelligence Settings
    EMBEDDING_PROVIDER: str = "hybrid"  # "hybrid" (built-in, zero-dep), "openai", or "gemini"
    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str | None = None
    MAX_INDEXED_FILES_PER_REPO: int = 150
    MAX_FILE_SIZE_BYTES: int = 250000
    CODE_CHUNK_SIZE_LINES: int = 60
    CODE_CHUNK_OVERLAP_LINES: int = 10

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
