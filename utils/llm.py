"""LLM API wrappers using litellm."""

import os

from litellm import completion, get_model_info, token_counter

from utils.env import load_env_file

load_env_file()

DEFAULT_MODEL = os.environ.get("MONITOR_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_MAX_TOKENS = int(os.environ.get("MONITOR_MAX_OUTPUT_TOKENS", "1024"))


def get_max_input_tokens(model: str) -> int:
    """Look up a model's max input token limit.

    Args:
        model: Model identifier recognised by litellm (e.g. "claude-sonnet-4-20250514")

    Returns:
        Max input tokens, or 0 if the lookup fails
    """
    try:
        info = get_model_info(model)
        return info.get("max_input_tokens") or 0
    except Exception:
        return 0


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens for a text string using litellm's model-aware tokenizer.

    Uses litellm.token_counter which selects the correct tokenizer per model
    (tiktoken for OpenAI, Anthropic tokenizer for Claude, etc.).

    Args:
        text: Text string to count tokens for
        model: Model identifier (defaults to MONITOR_MODEL env var)

    Returns:
        Token count
    """
    model = model or DEFAULT_MODEL
    return token_counter(model=model, text=text)


def call_llm(
    prompt: str,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: int = 0,
    thinking: dict | None = None,
) -> dict:
    """Call an LLM using litellm.

    Args:
        prompt: The prompt to send to the LLM
        model: Model identifier (defaults to MONITOR_MODEL env var)
        max_tokens: Maximum tokens in response (defaults to MONITOR_MAX_OUTPUT_TOKENS)
        temperature: Temperature for sampling (default 0 for deterministic)
        thinking: Optional thinking config dict (e.g. {"type": "enabled", "budget_tokens": 1024})

    Returns:
        Dict with 'text' key on success, or 'error' key on failure
    """
    model = model or DEFAULT_MODEL
    max_tokens = max_tokens or DEFAULT_MAX_TOKENS

    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if thinking:
        kwargs["thinking"] = thinking

    try:
        response = completion(**kwargs)

        return {
            "text": response.choices[0].message.content,
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        return {"error": str(e), "text": None}


def call_llm_with_system(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: int = 0,
    thinking: dict | None = None,
) -> dict:
    """Call an LLM with separate system and user prompts.

    Args:
        system_prompt: The system prompt
        user_prompt: The user prompt
        model: Model identifier
        max_tokens: Maximum tokens in response
        temperature: Temperature for sampling
        thinking: Optional thinking config dict

    Returns:
        Dict with 'text' key on success, or 'error' key on failure
    """
    model = model or DEFAULT_MODEL
    max_tokens = max_tokens or DEFAULT_MAX_TOKENS

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if thinking:
        kwargs["thinking"] = thinking

    try:
        response = completion(**kwargs)

        return {
            "text": response.choices[0].message.content,
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        return {"error": str(e), "text": None}
