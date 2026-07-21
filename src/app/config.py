from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Enterprise configuration management layer using Pydantic Settings.
    Automatically parses environment variables matching field names case-insensitively.
    """
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    TOKEN_TTL_SECONDS: int = 300

    # Prioritise environment variables over default settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate at module level to cache disk/env I/O reads
settings = Settings()
