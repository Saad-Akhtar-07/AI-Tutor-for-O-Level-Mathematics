"""Bounded, validated completions via Groq and/or OpenRouter.

Historical class names are retained for compatibility with the tutor service.
Unvalidated tokens are never streamed to a learner or used to award marks.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import httpx2 as httpx

from ..config import Settings

logger = logging.getLogger(__name__)
_slots = threading.BoundedSemaphore(6)
_cooldown_lock = threading.Lock()
_cooldowns: dict[tuple[str, str], float] = {}


class OpenRouterError(RuntimeError):
    def __init__(self, message: str, code: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ModelCompletion:
    content: str
    actual_model: str
    usage: dict[str, Any]


def retry_after_seconds(value: str | None) -> float:
    try:
        return max(0, float(value))
    except (TypeError, ValueError):
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0


def _error(status: int, detail: str = "") -> OpenRouterError:
    code = {
        401: "provider_auth", 402: "provider_credits", 403: "provider_forbidden",
        408: "provider_timeout", 429: "provider_rate_limited",
    }.get(status, "provider_error" if status >= 500 else f"provider_http_{status}")
    if status == 404 and any(word in detail.lower() for word in ("data policy", "free model training")):
        code = "provider_data_policy"
    # Provider bodies may contain prompts. Never propagate their raw contents.
    return OpenRouterError(f"AI endpoint returned HTTP {status}.", code=code)


class OpenRouterClient:
    def __init__(self, settings: Settings, *, budget_seconds: float | None = None) -> None:
        self.settings = settings
        self.deadline = time.monotonic() + (
            budget_seconds if budget_seconds is not None else settings.tutor_chat_budget_seconds
        )

    def structured_completion(
        self, *, model: str, messages: list[dict[str, Any]], schema_name: str,
        json_schema: dict[str, Any], temperature: float = 0, max_tokens: int = 1200,
        fallback_models: list[str] | None = None, groq_model: str | None = None,
        groq_json_mode: bool = False,
        validate: Callable[[ModelCompletion], Any] | None = None,
    ) -> ModelCompletion:
        if not _slots.acquire(blocking=False):
            raise OpenRouterError("The tutor is busy. Try again shortly.", code="provider_busy")
        try:
            return asyncio.run(self._complete(
                model=model, messages=messages, schema_name=schema_name,
                json_schema=json_schema, temperature=temperature, max_tokens=max_tokens,
                fallback_models=fallback_models or [], groq_model=groq_model,
                groq_json_mode=groq_json_mode, validate=validate,
            ))
        finally:
            _slots.release()

    async def _complete(self, *, model, messages, schema_name, json_schema,
                        temperature, max_tokens, fallback_models, groq_model, groq_json_mode, validate):
        s = self.settings
        routes = []
        preference = s.ai_vision_provider if groq_json_mode else s.ai_text_provider
        if groq_model and preference != "openrouter":
            if s.groq_api_key:
                routes.append(("groq", "https://api.groq.com/openai/v1/chat/completions", s.groq_api_key, [groq_model]))
            elif preference == "groq":
                raise OpenRouterError("Groq is not configured.", code="missing_api_key")
        if s.openrouter_api_key:
            routes.append(("openrouter", s.openrouter_base_url, s.openrouter_api_key,
                           list(dict.fromkeys([model, *fallback_models]))))
        if not routes:
            raise OpenRouterError("AI tutoring is not configured.", code="missing_api_key")
        # At most two HTTP attempts per stage, including provider failover.
        if len(routes) == 1:
            routes *= 2
        last_error = OpenRouterError("AI tutoring is temporarily unavailable.")
        started = time.monotonic()
        async with httpx.AsyncClient() as client:
            for attempt, (provider, url, key, models) in enumerate(routes):
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise OpenRouterError("AI request deadline reached.", code="provider_timeout")
                cooldown_key = (url, hashlib.sha256(key.encode()).hexdigest())
                with _cooldown_lock:
                    cooling_down = _cooldowns.get(cooldown_key, 0) > time.monotonic()
                if cooling_down:
                    last_error = OpenRouterError("AI endpoint is cooling down.", code="provider_rate_limited")
                    continue
                payload = {
                    "messages": messages, "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_schema", "json_schema": {
                        "name": schema_name, "strict": True, "schema": json_schema,
                    }},
                }
                if provider == "openrouter":
                    # Promote a backup on retry after a slow/invalid primary.
                    retrying_provider = attempt > 0 and routes[attempt - 1][0] == provider
                    selected = models[1:] + models[:1] if retrying_provider and len(models) > 1 else models
                    payload["models"] = selected
                    payload["provider"] = {
                        "require_parameters": True, "allow_fallbacks": True,
                        "sort": "latency", "data_collection": s.openrouter_data_collection,
                    }
                else:
                    payload["model"] = models[0]
                    if groq_json_mode:
                        payload["response_format"] = {"type": "json_object"}
                        payload["messages"] = [
                            {"role": "system", "content": "Return only JSON matching this schema: " + json.dumps(json_schema)},
                            *messages,
                        ]
                    if models[0].startswith("openai/gpt-oss"):
                        payload["reasoning_effort"] = "low"
                try:
                    # Also stop a server that trickles bytes without finishing.
                    response = await asyncio.wait_for(client.post(
                        url, headers={"Authorization": f"Bearer {key}",
                                      "X-Title": "O Level Mathematics Tutor"},
                        json=payload, timeout=httpx.Timeout(min(remaining, s.openrouter_timeout_seconds), connect=5),
                    ), timeout=min(remaining, s.openrouter_timeout_seconds))
                    body = None
                    try:
                        body = response.json()
                    except ValueError:
                        pass
                    provider_error = body.get("error") if isinstance(body, dict) else None
                    if response.status_code >= 400 or provider_error:
                        error_body = provider_error if isinstance(provider_error, dict) else {}
                        status = response.status_code
                        if status < 400:
                            try:
                                status = int(error_body.get("code", 502))
                            except (TypeError, ValueError):
                                status = 502
                        last_error = _error(status, str(error_body.get("message", "")))
                        if status == 429 or (status == 503 and response.headers.get("retry-after")):
                            delay = retry_after_seconds(response.headers.get("retry-after")) or 20
                            with _cooldown_lock:
                                _cooldowns[cooldown_key] = time.monotonic() + delay
                        next_provider = routes[attempt + 1][0] if attempt + 1 < len(routes) else provider
                        if status == 403 or (status in {400, 401, 402, 404, 413, 422} and next_provider == provider):
                            raise last_error
                    else:
                        if not isinstance(body, dict):
                            raise ValueError("Invalid response envelope")
                        choices = body.get("choices") or []
                        choice = choices[0] if choices else {}
                        message = choice.get("message") or {}
                        if message.get("refusal") or choice.get("finish_reason") == "content_filter":
                            raise OpenRouterError("The AI provider declined this request.", code="provider_forbidden")
                        content = message.get("content")
                        if choice.get("finish_reason") == "length" or not isinstance(content, str) or not content.strip():
                            raise ValueError("Empty or truncated completion")
                        result = ModelCompletion(
                            content=content,
                            actual_model=("groq/" if provider == "groq" else "") + str(body.get("model") or models[0]),
                            usage={**(body.get("usage") if isinstance(body.get("usage"), dict) else {}),
                                   "provider": provider, "attempts": attempt + 1,
                                   "elapsed_ms": round((time.monotonic() - started) * 1000)},
                        )
                        if validate:
                            validate(result)
                        logger.info("AI completion stage=%s provider=%s model=%s attempts=%d elapsed_ms=%d",
                                    schema_name, provider, result.actual_model, attempt + 1, result.usage["elapsed_ms"])
                        return result
                except (asyncio.TimeoutError, httpx.TimeoutException):
                    last_error = OpenRouterError("AI endpoint timed out.", code="provider_timeout")
                except httpx.RequestError:
                    last_error = OpenRouterError("AI endpoint could not be reached.")
                except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                    last_error = OpenRouterError("Invalid AI response.", code="invalid_structured_output")
                except OpenRouterError as error:
                    if error.code not in {"invalid_structured_output", "invalid_marks"}:
                        raise
                    last_error = error
                logger.warning("AI attempt failed stage=%s provider=%s code=%s attempt=%d",
                               schema_name, provider, last_error.code, attempt + 1)
                if attempt + 1 < len(routes) and routes[attempt + 1][0] == provider:
                    delay = 0.2 + random.random() * 0.2
                    if self.deadline - time.monotonic() > delay:
                        await asyncio.sleep(delay)
        raise last_error
