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
    """
    Generate text using the Ollama backend.
    
    Parameters:
        model (str, optional): Model name to use. If not provided, uses the OLLAMA_MODEL environment variable or defaults to "llama3.1:8b".
    
    Returns:
        str: The generated text.
    """
    model_name = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"]


def _xai_generate(prompt: str) -> str:
    """
    Generate text using xAI's Grok model.
    
    Parameters:
    	prompt (str): The input prompt for the model.
    
    Returns:
    	str: The generated text.
    
    Raises:
    	ValueError: If XAI_API_KEY environment variable is not set.
    	ImportError: If the openai package is not installed.
    """
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
    Generate text using the configured LLM provider.
    
    Parameters:
        model (str, optional): The model to use for generation. Only applies to the Ollama provider; ignored when using xAI.
    
    Returns:
        str: The generated text from the LLM.
    """
    if LLM_PROVIDER == "xai":
        return _xai_generate(prompt)
    else:
        return _ollama_generate(prompt, model)


async def generate_async(prompt: str, model: Optional[str] = None) -> str:
    """
    Generate text from a prompt using the configured LLM provider.
    
    Returns:
    	str: The generated text.
    """
    return await asyncio.to_thread(generate, prompt, model)


def get_current_provider() -> str:
    """
    Return the currently configured LLM provider.
    
    Returns:
        str: The name of the current LLM provider.
    """
    return LLM_PROVIDER


def set_provider(provider: str):
    """
    Set the active LLM provider backend.
    """
    global LLM_PROVIDER
    LLM_PROVIDER = provider.lower()
