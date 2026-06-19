"""
LLM Provider Abstraction for CampaignOS v2

Supported providers:
- ollama (default, local)
- xai    (xAI Grok via OpenAI-compatible API)
"""

import asyncio
import os
from typing import Optional

import ollama

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-3-mini-beta")


async def _ollama_generate(prompt: str, model: Optional[str] = None) -> str:
    model_name = model or OLLAMA_MODEL
    response = await asyncio.to_thread(
        ollama.chat,
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"]


def _xai_generate(prompt: str) -> str:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY is not set")

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package is required for xAI provider. Run: pip install openai")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1"
    )

    response = client.chat.completions.create(
        model=XAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


async def generate(prompt: str, model: Optional[str] = None) -> str:
    """
    Unified generation function (async).
    Uses the provider defined in LLM_PROVIDER env var.

    Note: The model parameter is only used for the ollama provider and ignored for xai.
    """
    if LLM_PROVIDER == "xai":
        return _xai_generate(prompt)
    else:
        return await _ollama_generate(prompt, model)


async def generate_async(prompt: str, model: Optional[str] = None) -> str:
    """Async wrapper that runs the sync generate in a thread to avoid blocking."""
    return await asyncio.to_thread(generate, prompt, model)


def get_current_provider() -> str:
    return LLM_PROVIDER


SUPPORTED_PROVIDERS = {"ollama", "xai"}

def set_provider(provider: str):
    global LLM_PROVIDER
    provider_lower = provider.lower()
    supported_providers = ["ollama", "xai"]
    if provider_lower not in supported_providers:
        raise ValueError(f"Invalid provider '{provider}'. Supported providers: {', '.join(supported_providers)}")
    LLM_PROVIDER = provider_lower


async def load_models_from_db():
    """Load model settings from database and update runtime globals."""
    global OLLAMA_MODEL, XAI_MODEL
    from database import get_setting

    ollama_model = await get_setting("ollama_model")
    if ollama_model:
        OLLAMA_MODEL = ollama_model

    xai_model = await get_setting("xai_model")
    if xai_model:
        XAI_MODEL = xai_model


def set_models(ollama_model: Optional[str] = None, xai_model: Optional[str] = None):
    """Update runtime model settings."""
    global OLLAMA_MODEL, XAI_MODEL
    if ollama_model:
        OLLAMA_MODEL = ollama_model
    if xai_model:
        XAI_MODEL = xai_model
