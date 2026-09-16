import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx2 as httpx
import pytest

from backend.app.config import Settings
from backend.app.services import openrouter
from backend.app.services.openrouter import OpenRouterClient, OpenRouterError, retry_after_seconds
from backend.app.services.tutor import _parse_model
from backend.app.schemas.tutor import SocraticReply


def settings(**overrides):
    values = dict(database_url="postgresql://unused", cors_origins=[],
                  openrouter_api_key="test-key", openrouter_base_url="https://example.invalid/completions",
                  openrouter_vision_model="vision:free", openrouter_evaluation_model="evaluation:free",
                  openrouter_chat_model="chat:free", openrouter_data_collection="deny",
                  openrouter_timeout_seconds=1)
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(autouse=True)
def clear_cooldowns():
    openrouter._cooldowns.clear()
    yield
    openrouter._cooldowns.clear()


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(openrouter.httpx, "AsyncClient", lambda: original(transport=httpx.MockTransport(handler)))


def success(content="{}", **kwargs):
    return httpx.Response(200, json={"model": "actual", "choices": [
        {"message": {"content": content}, "finish_reason": "stop"}], **kwargs})


def completion(client, **kwargs):
    return client.structured_completion(model="chat:free", messages=[{"role": "user", "content": "hello"}],
                                        schema_name="test_reply", json_schema={"type": "object"}, **kwargs)


def test_latency_routing_privacy_token_cap_and_free_fallbacks(monkeypatch):
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        return success()
    transport(monkeypatch, handler)
    completion(OpenRouterClient(settings()), fallback_models=["backup:free"])
    payload = captured[0]
    assert payload["models"] == ["chat:free", "backup:free"]
    assert payload["provider"] == {"require_parameters": True, "allow_fallbacks": True,
                                   "sort": "latency", "data_collection": "deny"}
    assert payload["max_tokens"] == 1200


@pytest.mark.parametrize("status,code", [(401,"provider_auth"),(402,"provider_credits"),
    (403,"provider_forbidden"),(400,"provider_http_400"),(404,"provider_data_policy")])
def test_permanent_errors_fail_fast_without_leaking_body(monkeypatch, status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "No endpoints matching data policy SECRET"}})
    transport(monkeypatch, handler)
    with pytest.raises(OpenRouterError) as error:
        completion(OpenRouterClient(settings()))
    assert error.value.code == code
    assert "SECRET" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("status", [408, 500, 502, 503])
def test_transient_error_recovers_with_promoted_backup(monkeypatch, status):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(status) if len(calls) == 1 else success()
    transport(monkeypatch, handler)
    result = completion(OpenRouterClient(settings()), fallback_models=["backup:free"])
    assert result.usage["attempts"] == 2
    assert calls[1]["models"][0] == "backup:free"


@pytest.mark.parametrize("status", [200, 429])
def test_rate_limit_including_http_200_stops_retry_storm(monkeypatch, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": 429}}, headers={"retry-after": "60"})
    transport(monkeypatch, handler)
    for _ in range(2):
        with pytest.raises(OpenRouterError) as error:
            completion(OpenRouterClient(settings()))
        assert error.value.code == "provider_rate_limited"
    assert len(calls) == 1


def test_groq_rate_limit_fails_over_without_sending_key_to_openrouter(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.host == "api.groq.com":
            return httpx.Response(429, headers={"retry-after": "60"})
        return success()
    transport(monkeypatch, handler)
    result = completion(OpenRouterClient(settings(groq_api_key="groq-key")), groq_model="openai/gpt-oss-20b")
    assert result.usage["provider"] == "openrouter"
    assert requests[0].headers["authorization"] == "Bearer groq-key"
    assert requests[1].headers["authorization"] == "Bearer test-key"
    assert "provider" not in json.loads(requests[0].content)


def test_groq_works_without_openrouter_key(monkeypatch):
    transport(monkeypatch, lambda request: success())
    result = completion(OpenRouterClient(settings(groq_api_key="groq-key", openrouter_api_key="")),
                        groq_model="openai/gpt-oss-20b")
    assert result.actual_model == "groq/actual"


@pytest.mark.parametrize("bad", [None, [], {"choices": []}, {"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]}])
def test_bad_envelopes_retry_once(monkeypatch, bad):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=json.dumps(bad)) if len(calls) == 1 else success()
    transport(monkeypatch, handler)
    assert completion(OpenRouterClient(settings())).usage["attempts"] == 2


def test_schema_invalid_reply_retries_before_reaching_student(monkeypatch):
    calls = []
    reply = dict(message="How many counters are there?", teaching_move="ask_question",
                 should_revise_work=False, reveals_final_answer=False)
    def handler(request):
        calls.append(request)
        return success("{}" if len(calls) == 1 else json.dumps(reply))
    transport(monkeypatch, handler)
    result = completion(OpenRouterClient(settings()), validate=lambda c: _parse_model(SocraticReply,c))
    assert len(calls) == 2
    assert _parse_model(SocraticReply,result).message == reply["message"]


def test_total_deadline_cancels_slow_call_and_is_shared_between_stages(monkeypatch):
    cancelled = []
    async def handler(request):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
    transport(monkeypatch, handler)
    client = OpenRouterClient(settings(), budget_seconds=0.04)
    start = time.monotonic()
    for _ in range(2):
        with pytest.raises(OpenRouterError) as error:
            completion(client)
        assert error.value.code == "provider_timeout"
    assert time.monotonic() - start < 0.5
    assert len(cancelled) == 1


def test_retry_after_supports_http_date_and_invalid_headers():
    assert retry_after_seconds("60") == 60
    assert retry_after_seconds("invalid") == 0
    assert retry_after_seconds(None) == 0
    assert 25 < retry_after_seconds(format_datetime(datetime.now(timezone.utc)+timedelta(seconds=30))) <= 30


def test_concurrency_limit_fails_fast(monkeypatch):
    slots = openrouter.threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(openrouter, "_slots", slots)
    with pytest.raises(OpenRouterError) as error:
        completion(OpenRouterClient(settings()))
    assert error.value.code == "provider_busy"
