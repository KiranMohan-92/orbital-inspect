from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    REDIS_URL: str = "redis://localhost:6379"
    DEMO_MODE: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./orbital_inspect.db"

    # Auth (Sprint 3)
    AUTH_ENABLED: bool = False
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_EXPIRY_MINUTES: int = 60

    # Resilience
    AGENT_TIMEOUT_SECONDS: int = 120
    GEMINI_CIRCUIT_BREAKER_THRESHOLD: int = 5
    JOB_TIMEOUT_SECONDS: int = 300

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "console"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
