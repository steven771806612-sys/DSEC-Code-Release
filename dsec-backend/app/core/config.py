from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_NAME: str = "DSEC AI Case Review System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dsec"
    DATABASE_ECHO: bool = False

    # JWT
    JWT_SECRET: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_DIMENSION: int = 1536

    # S3
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "dsec-attachments"
    S3_REGION: str = "us-east-1"
    S3_PRESIGN_EXPIRE_SECONDS: int = 900

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@dsec.dji.com"
    SMTP_TLS: bool = False

    # RAG
    RAG_TOP_K_RUBRIC: int = 5
    RAG_TOP_K_CASES: int = 5
    RAG_TOP_K_REVIEWS: int = 3
    RAG_TOP_K_DISAGREEMENTS: int = 2
    RAG_CONFIDENCE_THRESHOLD: float = 0.6
    DISAGREEMENT_MAJOR_THRESHOLD: float = 20.0
    DISAGREEMENT_CRITICAL_THRESHOLD: float = 25.0

    # SLA
    SLA_PLATFORM_REVIEW_HOURS: int = 48
    SLA_DJI_REVIEW_HOURS: int = 72
    CASE_WITHDRAW_WINDOW_MINUTES: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
