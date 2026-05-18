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
    return {
        "provider": name,
        "active_default": settings.OLLAMA_MODEL if name == "ollama" else settings.OPENROUTER_MODEL,
        "models": models,
    }
