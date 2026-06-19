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


def _ollama_generate(prompt: str, model: Optional[str] = None) -> str:
    model_name = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    response = ollama.chat(
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

    model = os.getenv("XAI_MODEL", "grok-3-mini-beta")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def generate(prompt: str, model: Optional[str] = None) -> str:
    """
    Unified generation function (sync).
    Uses the provider defined in LLM_PROVIDER env var.
    """
    if LLM_PROVIDER == "xai":
        return _xai_generate(prompt)
    else:
        return _ollama_generate(prompt, model)


async def generate_async(prompt: str, model: Optional[str] = None) -> str:
    """Async wrapper that runs the sync generate in a thread to avoid blocking."""
    return await asyncio.to_thread(generate, prompt, model)


def get_current_provider() -> str:
    return LLM_PROVIDER


SUPPORTED_PROVIDERS = {"ollama", "xai"}

def set_provider(provider: str):
    global LLM_PROVIDER
    normalized = provider.lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider '{provider}'. Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}")
    LLM_PROVIDER = normalized
