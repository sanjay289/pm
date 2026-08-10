import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# In Docker, OPENROUTER_API_KEY is already injected via docker-compose's
# env_file. For local `uv run` (cwd is backend/), load the root .env
# explicitly; a missing file here is a no-op, not an error.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


class OpenRouterError(Exception):
    pass


def _get_api_key() -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set")
    return api_key


def _post_chat_completion(
    messages: list[dict[str, str]], response_format: dict[str, Any] | None = None
) -> dict[str, Any]:
    api_key = _get_api_key()
    payload: dict[str, Any] = {"model": MODEL, "messages": messages}
    if response_format is not None:
        payload["response_format"] = response_format

    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise OpenRouterError(f"Network error calling OpenRouter: {exc}") from exc

    if response.status_code != 200:
        raise OpenRouterError(
            f"OpenRouter request failed with status {response.status_code}: {response.text}"
        )

    return response.json()


def _extract_content(data: dict[str, Any]) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc


def complete(messages: list[dict[str, str]]) -> str:
    return _extract_content(_post_chat_completion(messages))


def complete_structured(messages: list[dict[str, str]], schema_name: str, schema: dict[str, Any]) -> str:
    """Like `complete`, but requests (and returns, still as a string) a
    response conforming to `schema` via OpenRouter's structured outputs."""
    data = _post_chat_completion(
        messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
    )
    return _extract_content(data)
