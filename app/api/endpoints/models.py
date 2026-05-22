from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services.llm import LLMProviderError, get_provider

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models(
    provider: str | None = Query(default=None, description="Override provider for discovery"),
) -> dict:
    name = (provider or settings.LLM_PROVIDER).lower()
    try:
        prov = get_provider(provider=name)
        models = await prov.list_models()
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    configured_default = (
        settings.OLLAMA_MODEL if name == "ollama" else settings.OPENROUTER_MODEL
    )
    # Only advertise the configured default if it is actually installed; otherwise
    # the UI's "Default (...)" option would queue a translation for a model that
    # Ollama 404s on. Fall back to the first installed model, or None.
    if configured_default in models:
        active_default = configured_default
    else:
        active_default = models[0] if models else None

    # In two-stage mode the per-stage defaults are what actually run.
    stage_defaults = {
        "stage1": settings.OLLAMA_STAGE1_MODEL,
        "stage2": settings.OLLAMA_STAGE2_MODEL,
    }
    return {
        "provider": name,
        "pipeline": settings.TRANSLATION_PIPELINE,
        "configured_default": configured_default,
        "active_default": active_default,
        "stage_defaults": stage_defaults,
        "models": models,
    }
