from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    REDIS_URL: str = "redis://localhost:6379"
    DEMO_MODE: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./orbital_inspect.db"

    # Auth
    AUTH_ENABLED: bool = False
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_EXPIRY_MINUTES: int = 60

    @model_validator(mode="after")
    def validate_jwt_secret(self):
        if self.AUTH_ENABLED and self.JWT_SECRET == "dev-secret-change-in-production":
            raise ValueError(
                "JWT_SECRET must be set to a strong random value when AUTH_ENABLED=true. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )
        return self

    # Resilience
    AGENT_TIMEOUT_SECONDS: int = 120
    GEMINI_CIRCUIT_BREAKER_THRESHOLD: int = 5
    JOB_TIMEOUT_SECONDS: int = 300

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "console"

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
        "http://localhost:5176", "http://localhost:5177", "http://localhost:3000",
    ]


settings = Settings()
