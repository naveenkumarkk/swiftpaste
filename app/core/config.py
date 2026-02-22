from typing import Any
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    API_PREFIX: str = Field(default="/api")
    DEBUG: bool = Field(default=False)

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/swiftpaste"
    )
    DATABASE_SYNC_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/swiftpaste"
    )

    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ]
    )

    ENV: str = Field(default="dev")

    JWT_SECRET: str = "N@een+Pr@nesh28"
    JWT_LIFETIME_SECONDS: int = 3600

    RESET_PASSWORD_TOKEN_SECRET: str = "naveenpranesh"
    VERIFICATION_TOKEN_SECRET: str = "naveenpranesh28"

    GOOGLE_CLIENT_ID: str = Field(default="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="GOOGLE_CLIENT_SECRET")

    REQUEST_ID_HEADER = "X-Request-Id"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v

        if v is None:
            return []

        s = str(v).strip()

        if s in ("*", "[*]", "['*']", '["*"]'):
            return ["*"]

        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1].strip()

        items = [x.strip().strip("'").strip('"') for x in s.split(",") if x.strip()]
        return items

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
