from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    REDIS_URL: str = "redis://localhost:6379"
    DEMO_MODE: bool = True


settings = Settings()
