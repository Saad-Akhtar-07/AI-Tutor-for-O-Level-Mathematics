"""
openrouter_client.py – thin wrapper around the OpenRouter chat-completions API.

Only uses the `requests` library.  No LLM framework is introduced.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from .config import (
    MAX_RETRIES,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    RETRY_BASE_SECONDS,
)

# HTTP timeout (seconds) for a single API call.
# Vision requests with a large base64 image can take a while.
REQUEST_TIMEOUT = 120


class OpenRouterError(Exception):
    """Raised when all retries are exhausted for an API call."""


def _post_completion(
    messages: List[Dict[str, Any]],
    model: str = OPENROUTER_MODEL,
) -> Dict[str, Any]:
    """
    Send one chat-completion request (no retry logic here – callers handle that).

    Raises
    ------
    requests.HTTPError   – for 4xx / 5xx responses (after raising_for_status).
    requests.Timeout     – if the server does not respond within REQUEST_TIMEOUT.
    requests.RequestException – for lower-level network errors.
    """
    if not OPENROUTER_API_KEY:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is not set.  "
            "Add it to your .env file and try again."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # Recommended by OpenRouter for analytics/debugging.
        "HTTP-Referer": "https://github.com/local/notes-parser",
        "X-Title": "Notes PDF Parser",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        # Instruct the model to return a JSON object.
        "response_format": {"type": "json_object"},
    }

    response = requests.post(
        OPENROUTER_BASE_URL,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def call_vision_model(
    system_prompt: str,
    user_content: List[Dict[str, Any]],
    page_number: int,
    model: str = OPENROUTER_MODEL,
) -> str:
    """
    Call the OpenRouter vision model with retry/backoff.

    Returns
    -------
    The raw content string from choices[0].message.content.

    Raises
    ------
    OpenRouterError  – if all retries are exhausted.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content},
    ]

    last_exc: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _post_completion(messages, model=model)
            if not isinstance(result, dict):
                raise requests.RequestException(f"Invalid response type from OpenRouter: {type(result).__name__}")

            if "error" in result:
                err_msg = result["error"].get("message") if isinstance(result["error"], dict) else str(result["error"])
                raise requests.RequestException(f"OpenRouter API error response: {err_msg}")

            choices = result.get("choices")
            if not choices or not isinstance(choices, list):
                raise requests.RequestException("No choices returned in OpenRouter response")

            message = choices[0].get("message", {})
            raw_content = message.get("content")
            if not raw_content or not isinstance(raw_content, str) or not raw_content.strip():
                raise requests.RequestException("OpenRouter returned null or empty message content")

            return raw_content

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            last_exc = exc
            if status == 429 or (isinstance(status, int) and status >= 500):
                _wait_and_log(attempt, f"HTTP {status}", page_number)
            else:
                # 4xx that are not rate-limits are not retryable.
                raise OpenRouterError(
                    f"Non-retryable HTTP error {status} on page {page_number}: {exc}"
                ) from exc

        except (requests.Timeout, requests.RequestException) as exc:
            last_exc = exc
            _wait_and_log(attempt, str(exc), page_number)

    raise OpenRouterError(
        f"Page {page_number}: all {MAX_RETRIES} API attempts failed.  "
        f"Last error: {last_exc}"
    )


def _wait_and_log(attempt: int, reason: str, page_number: int) -> None:
    wait = RETRY_BASE_SECONDS * (2 ** (attempt - 1))   # 2 → 4 → 8 seconds
    print(
        f"  Page {page_number}: attempt {attempt} failed ({reason}).  "
        f"Retrying in {wait:.0f}s…"
    )
    time.sleep(wait)
