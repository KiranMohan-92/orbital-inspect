import base64
import hashlib
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"  # development | staging | production | test
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    REDIS_URL: str = "redis://localhost:6379"
    DEMO_MODE: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./orbital_inspect.db"
    DATABASE_AUTO_INIT: bool = False
    DATA_DIR: str = "./data"
    UPLOADS_DIR: str | None = None
    DEMO_CACHE_DIR: str | None = None
    DEMO_IMAGES_DIR: str | None = None
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_LOCAL_ROOT: str | None = None
    STORAGE_BUCKET: str | None = None
    STORAGE_REGION: str = "us-east-1"
    STORAGE_ENDPOINT_URL: str | None = None
    STORAGE_ACCESS_KEY_ID: str | None = None
    STORAGE_SECRET_ACCESS_KEY: str | None = None
    STORAGE_PREFIX: str = "orbital-inspect"
    STORAGE_FORCE_PATH_STYLE: bool = True
    STORAGE_CREATE_BUCKET: bool = False
    SIGNED_ARTIFACT_TTL_MINUTES: int = 30
    REPORT_ARTIFACT_RETENTION_DAYS: int = 30

    # Queueing
    ANALYSIS_QUEUE_NAME: str = "arq:queue"
    ANALYSIS_JOB_MAX_RETRIES: int = 3
    ANALYSIS_RETRY_BACKOFF_BASE_SECONDS: int = 5
    REDIS_REQUIRED: bool = False

    # Auth
    AUTH_ENABLED: bool | None = None
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_PREVIOUS_SECRETS: list[str] = []
    JWT_EXPIRY_MINUTES: int = 60
    JWT_ISSUER: str = "orbital-inspect"
    JWT_AUDIENCE: str = "orbital-inspect-api"
    API_KEY_PREFIX: str = "oi"
    WEBHOOK_SECRET_ENCRYPTION_KEY: str | None = None
    WEBHOOK_SECRET_PREVIOUS_KEYS: list[str] = []

    @model_validator(mode="after")
    def validate_jwt_secret(self):
        if self.AUTH_ENABLED is None:
            self.AUTH_ENABLED = not self.DEMO_MODE
        if self.E2E_TEST_MODE:
            self.DATABASE_AUTO_INIT = True
        if self.APP_ENV in {"staging", "production"} and self.DEMO_MODE:
            raise ValueError("DEMO_MODE must be false in staging and production environments")
        if self.APP_ENV in {"staging", "production"} and not self.AUTH_ENABLED:
            raise ValueError("AUTH_ENABLED must be true in staging and production environments")
        if self.APP_ENV in {"staging", "production"} and not self.WEBHOOK_SECRET_ENCRYPTION_KEY:
            raise ValueError("WEBHOOK_SECRET_ENCRYPTION_KEY must be set in staging and production environments")
        if self.AUTH_ENABLED and self.JWT_SECRET == "dev-secret-change-in-production":
            raise ValueError(
                "JWT_SECRET must be set to a strong random value when AUTH_ENABLED=true. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )
        if self.STORAGE_BACKEND not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be one of: local, s3")
        if self.STORAGE_BACKEND == "s3" and not self.STORAGE_BUCKET:
            raise ValueError("STORAGE_BUCKET must be set when STORAGE_BACKEND=s3")
        if self.APP_ENV not in {"development", "staging", "production", "test"}:
            raise ValueError("APP_ENV must be one of: development, staging, production, test")
        return self

    # Resilience
    AGENT_TIMEOUT_SECONDS: int = 120
    GEMINI_CIRCUIT_BREAKER_THRESHOLD: int = 5
    JOB_TIMEOUT_SECONDS: int = 300
    E2E_TEST_MODE: bool = False
    MIN_EVIDENCE_COMPLETENESS_FOR_DECISION: float = 80.0
    REQUIRE_HUMAN_REVIEW_FOR_DECISIONS: bool = True
    GOVERNANCE_POLICY_VERSION: str = "2026-04-03"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "console"
    METRICS_ENABLED: bool = True
    PROMETHEUS_METRICS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_REQUIRED: bool = False
    OTEL_SERVICE_NAME: str = "orbital-inspect"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_EXPORTER_OTLP_HEADERS: str = ""
    OTEL_RESOURCE_ATTRIBUTES: str = ""
    OTEL_TRACES_SAMPLER_RATIO: float = 1.0
    OTEL_CONSOLE_EXPORTER: bool = False
    OBSERVABILITY_SHARED_TOKEN: str | None = None
    OBSERVABILITY_PREVIOUS_TOKENS: list[str] = []

    # Rate limiting
    RATE_LIMIT_BACKEND: str = "memory"  # memory | redis
    ANALYSIS_RATE_LIMIT_PER_HOUR: int = 20
    REPORT_RATE_LIMIT_PER_HOUR: int = 60
    RATE_LIMIT_FAIL_OPEN: bool = True

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
        "http://localhost:5176", "http://localhost:5177", "http://localhost:4173",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175",
        "http://127.0.0.1:5176", "http://127.0.0.1:5177", "http://127.0.0.1:4173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ]

    @property
    def data_dir_path(self) -> Path:
        return Path(self.DATA_DIR).expanduser().resolve()

    @property
    def uploads_dir_path(self) -> Path:
        base = self.UPLOADS_DIR or str(self.data_dir_path / "uploads")
        return Path(base).expanduser().resolve()

    @property
    def storage_local_root_path(self) -> Path:
        base = self.STORAGE_LOCAL_ROOT or self.UPLOADS_DIR or str(self.data_dir_path / "storage")
        return Path(base).expanduser().resolve()

    @property
    def demo_cache_dir_path(self) -> Path:
        base = self.DEMO_CACHE_DIR or str(self.data_dir_path / "demo_cache")
        return Path(base).expanduser().resolve()

    @property
    def demo_images_dir_path(self) -> Path:
        base = self.DEMO_IMAGES_DIR or str(self.data_dir_path / "demo_images")
        return Path(base).expanduser().resolve()

    @property
    def webhook_secret_encryption_keys(self) -> list[str]:
        configured = [
            key
            for key in [self.WEBHOOK_SECRET_ENCRYPTION_KEY, *self.WEBHOOK_SECRET_PREVIOUS_KEYS]
            if key
        ]
        if configured:
            return configured
        digest = hashlib.sha256(f"orbital-inspect-webhooks:{self.JWT_SECRET}".encode("utf-8")).digest()
        return [base64.urlsafe_b64encode(digest).decode("ascii")]

    @property
    def observability_tokens(self) -> list[str]:
        return [token for token in [self.OBSERVABILITY_SHARED_TOKEN, *self.OBSERVABILITY_PREVIOUS_TOKENS] if token]


settings = Settings()
