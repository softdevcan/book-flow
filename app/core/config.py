from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./bookflow.db"

    LLM_PROVIDER: Literal["ollama", "openrouter"] = "ollama"

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_TEMPERATURE: float = 0.4
    OLLAMA_TIMEOUT_SECONDS: float = 180.0
    OLLAMA_NUM_PREDICT: int = 4096
    OLLAMA_NUM_CTX: int = 8192
    # Force Ollama's JSON mode (`format="json"`). Most models behave better with it
    # because output is guaranteed parseable. Some models (aya-expanse) tend to close
    # the JSON early; if you hit truncation, try setting this to False — but then
    # unescaped quotes inside dialogue may break parsing.
    OLLAMA_FORCE_JSON_FORMAT: bool = True

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str | None = None

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])


settings = Settings()
