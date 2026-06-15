from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict,  NoDecode
from typing import Annotated

allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://localhost:3000"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def _default_database_url() -> str:
    if _running_in_docker():
        return "postgresql://postgres:postgres@host.docker.internal:5433/amazon_prism"
    return "postgresql://postgres:postgres@127.0.0.1:5433/amazon_prism"


def _default_minio_endpoint() -> str:
    if _running_in_docker():
        return "host.docker.internal:9000"
    return "localhost:9000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = _default_database_url()
    minio_endpoint: str = _default_minio_endpoint()
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "amazon-prism"
    minio_secure: bool = False
    minio_public_base_url: str = "http://localhost:9000"
    app_name: str = "Amazon Prism Backend"
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://localhost:3000"]
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    # vision provider: bedrock (AWS-native) | gemini | stub
    vision_provider: str = "bedrock"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.amazon.nova-lite-v1:0"
    # object storage region (used when pointing the S3-compatible client at AWS S3)
    minio_region: str = "us-east-1"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        cleaned = value.strip().strip("[]")
        return [origin.strip().strip("'\"") for origin in cleaned.split(",") if origin.strip()]

    @field_validator("minio_endpoint", mode="before")
    @classmethod
    def normalize_minio_endpoint(cls, value: str) -> str:
        return value.replace("http://", "").replace("https://", "").rstrip("/")

    @field_validator("minio_public_base_url", mode="before")
    @classmethod
    def normalize_public_base_url(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
