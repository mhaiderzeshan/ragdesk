from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, model_validator
from typing import Optional


class Settings(BaseSettings):
    
    DATABASE_URL: Optional[str] = None  

    DB_USER: Optional[str] = None       # Local docker-compose
    DB_PASSWORD: Optional[SecretStr] = None
    DB_HOST: Optional[str] = "localhost"
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None

    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if self.DATABASE_URL:
            
            if self.DATABASE_URL.startswith("postgresql://"):
                self.DATABASE_URL = self.DATABASE_URL.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            return self

        # Fall back to building URL from individual parts
        if not all([self.DB_USER, self.DB_PASSWORD, self.DB_NAME]):
            raise ValueError(
                "Either DATABASE_URL or DB_USER + DB_PASSWORD + DB_NAME must be set"
            )
        password = self.DB_PASSWORD.get_secret_value()
        self.DATABASE_URL = (
            f"postgresql+asyncpg://{self.DB_USER}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        return self

    # --- Auth ---
    SECRET_KEY: SecretStr
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- File uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    # --- Cloudflare R2 ---
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: SecretStr
    R2_BUCKET_NAME: str = "ragdesk-docs"

    @property
    def R2_ENDPOINT_URL(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    # --- Redis ---
    REDIS_URL: str

    # --- AI Keys ---
    GOOGLE_API_KEY: SecretStr
    GROQ_API_KEY: SecretStr

    CORS_ORIGINS: list[str] = []

    OTEL_EXPORTER: str = "console"
    OTEL_ENDPOINT: str = ""

    # When True, the SQLAlchemy engine echoes every statement (dev only).
    # Keep False in production — echoing leaks query text + parameters to logs.
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()  # type: ignore