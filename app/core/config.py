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

    # Translation pipeline strategy.
    # "single"    — one LLM pass (the original behavior).
    # "two_stage" — Builder (faithful EN->TR) then Artist (literary refinement).
    TRANSLATION_PIPELINE: Literal["single", "two_stage"] = "single"

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    # Two-stage models. Empty by default ON PURPOSE: no model is hardcoded, so the
    # UI must pick installed models per request. If both these and the request
    # override are empty, the translate endpoint rejects the request (400) rather
    # than silently falling back to a model that may not be installed.
    OLLAMA_STAGE1_MODEL: str = ""
    OLLAMA_STAGE2_MODEL: str = ""
    OLLAMA_TEMPERATURE: float = 0.4
    # Raised from 180 to cover two sequential passes plus Ollama model-swap latency.
    OLLAMA_TIMEOUT_SECONDS: float = 400.0
    OLLAMA_NUM_PREDICT: int = 4096
    OLLAMA_NUM_CTX: int = 8192
    # Reasoning ("think") toggle for reasoning models (qwen3.x etc.). OFF by default:
    # translation needs no chain-of-thought, and long reasoning both slows the call
    # and can exhaust num_predict before the model emits the JSON answer (leaving
    # `content` empty). Set true only if you specifically want the model to reason.
    OLLAMA_THINK: bool = False
    # Force Ollama's JSON mode (`format="json"`). Most models behave better with it
    # because output is guaranteed parseable. Some models (aya-expanse) tend to close
    # the JSON early; if you hit truncation, try setting this to False — but then
    # unescaped quotes inside dialogue may break parsing.
    OLLAMA_FORCE_JSON_FORMAT: bool = True

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str | None = None

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])


settings = Settings()
