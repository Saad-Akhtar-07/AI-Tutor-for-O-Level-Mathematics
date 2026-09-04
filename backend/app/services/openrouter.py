from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from ..config import Settings


class OpenRouterError(RuntimeError):
    def __init__(self, message: str, code: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ModelCompletion:
    content: str
    actual_model: str
    usage: dict[str, Any]


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def structured_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        schema_name: str,
        json_schema: dict[str, Any],
        temperature: float = 0,
    ) -> ModelCompletion:
        if not self.settings.openrouter_api_key:
            raise OpenRouterError(
                "AI review is not configured yet.", code="missing_api_key"
            )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            },
            "provider": {
                "require_parameters": True,
                "data_collection": self.settings.openrouter_data_collection,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ai-mathematics-tutor",
            "X-Title": "O Level Mathematics Tutor",
        }

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = requests.post(
                    self.settings.openrouter_base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.openrouter_timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(
                        f"OpenRouter returned HTTP {response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                body = response.json()
                if body.get("error"):
                    raise OpenRouterError("The AI provider rejected the review request.")
                choices = body.get("choices") or []
                content = (choices[0].get("message") or {}).get("content") if choices else None
                if not isinstance(content, str) or not content.strip():
                    raise OpenRouterError("The AI provider returned an empty response.")
                return ModelCompletion(
                    content=content,
                    actual_model=str(body.get("model") or model),
                    usage=body.get("usage") if isinstance(body.get("usage"), dict) else {},
                )
            except (requests.Timeout, requests.ConnectionError) as error:
                last_error = error
            except requests.HTTPError as error:
                last_error = error
                if error.response is not None and error.response.status_code < 500 and error.response.status_code != 429:
                    provider_detail = "request rejected"
                    try:
                        error_body = error.response.json()
                        if isinstance(error_body.get("error"), dict):
                            provider_detail = str(
                                error_body["error"].get("message") or provider_detail
                            )
                    except (ValueError, AttributeError, TypeError):
                        pass
                    error_code = f"provider_http_{error.response.status_code}"
                    lowered_detail = provider_detail.lower()
                    if error.response.status_code == 404 and (
                        "data policy" in lowered_detail
                        or "free model training" in lowered_detail
                    ):
                        error_code = "provider_data_policy"
                    raise OpenRouterError(
                        f"OpenRouter HTTP {error.response.status_code}: "
                        f"{provider_detail[:500]}",
                        code=error_code,
                    ) from error
            except (ValueError, KeyError, TypeError) as error:
                last_error = error
            if attempt == 0:
                time.sleep(1)

        if (
            isinstance(last_error, requests.HTTPError)
            and last_error.response is not None
            and last_error.response.status_code == 429
        ):
            raise OpenRouterError(
                "OpenRouter's current model quota is exhausted or rate-limited.",
                code="provider_rate_limited",
            ) from last_error

        detail = str(last_error)[:300] if last_error else "unknown provider error"
        raise OpenRouterError(
            f"The AI provider is temporarily unavailable: {detail}"
        ) from last_error
