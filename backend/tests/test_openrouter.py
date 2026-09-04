import requests
import pytest

from backend.app.config import Settings
from backend.app.services.openrouter import OpenRouterClient, OpenRouterError


def settings(data_collection: str = "deny") -> Settings:
    return Settings(
        database_url="postgresql://unused",
        cors_origins=[],
        openrouter_api_key="test-key",
        openrouter_base_url="https://example.invalid/chat/completions",
        openrouter_vision_model="test-vision",
        openrouter_evaluation_model="test-evaluation",
        openrouter_chat_model="test-chat",
        openrouter_data_collection=data_collection,
        openrouter_timeout_seconds=1,
    )


class FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}", response=self
            )


def completion(client: OpenRouterClient):
    return client.structured_completion(
        model="test-chat",
        messages=[{"role": "user", "content": "hello"}],
        schema_name="test_reply",
        json_schema={"type": "object", "properties": {}},
    )


def test_openrouter_sends_configured_data_policy(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(json)
        return FakeResponse(
            200,
            {
                "model": "test-chat",
                "choices": [{"message": {"content": "{}"}}],
                "usage": {},
            },
        )

    monkeypatch.setattr(requests, "post", fake_post)
    completion(OpenRouterClient(settings("allow")))
    assert captured["provider"]["data_collection"] == "allow"
    assert captured["provider"]["require_parameters"] is True


def test_openrouter_classifies_rate_and_privacy_failures(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.services.openrouter.time.sleep", lambda _: None)
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(429, {"error": {"message": "limited"}}),
    )
    with pytest.raises(OpenRouterError) as rate_error:
        completion(OpenRouterClient(settings()))
    assert rate_error.value.code == "provider_rate_limited"

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            404,
            {"error": {"message": "No endpoints found matching your data policy"}},
        ),
    )
    with pytest.raises(OpenRouterError) as privacy_error:
        completion(OpenRouterClient(settings()))
    assert privacy_error.value.code == "provider_data_policy"
