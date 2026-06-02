from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "ultimate-assistant"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"
    MASTER_ENCRYPTION_KEYS: str = ""  # comma-separated Fernet keys; newest first for rotation

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    LOG_LEVEL: str = "info"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ultimate_assistant"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "ultimate-assistant"
    S3_ENDPOINT_URL: str | None = None

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # CORS — comma-separated list of allowed origins (used when not in DEBUG)
    CORS_ORIGINS: str = ""

    # Password policy
    PASSWORD_MIN_LENGTH: int = 8

    # Account lockout
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_SECONDS: int = 900  # 15 minutes

    # OpenTelemetry
    OTEL_EXPORTER_ENDPOINT: str | None = None  # e.g. http://localhost:4317

    # Guardrails
    GUARDRAILS_ENABLED: bool = True
    MAX_INPUT_TOKENS_FREE: int = 4096
    MAX_INPUT_TOKENS_PRO: int = 32768
    MAX_INPUT_TOKENS_ENTERPRISE: int = 131072

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.is_production:
            if self.SECRET_KEY in ("", "change-me"):
                raise ValueError("SECRET_KEY must be set to a strong value in production")
            if not self.MASTER_ENCRYPTION_KEYS:
                raise ValueError("MASTER_ENCRYPTION_KEYS must be set in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
        return self


settings = Settings()
