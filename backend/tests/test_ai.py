import os
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import OpenRouterError, complete
from app.main import app

VALID_CREDENTIALS = {"username": "user", "password": "password"}


def test_complete_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(OpenRouterError, match="not set"):
        complete([{"role": "user", "content": "hi"}])


def test_complete_raises_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("boom")))

    with pytest.raises(OpenRouterError, match="Network error"):
        complete([{"role": "user", "content": "hi"}])


def test_complete_raises_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class FakeResponse:
        status_code = 401
        text = "unauthorized"

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(OpenRouterError, match="401"):
        complete([{"role": "user", "content": "hi"}])


def test_complete_raises_on_unexpected_response_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self) -> dict:
            return {}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(OpenRouterError, match="Unexpected"):
        complete([{"role": "user", "content": "hi"}])


@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set")
def test_complete_real_2_plus_2() -> None:
    reply = complete([{"role": "user", "content": "What is 2+2? Answer with just the number."}])

    assert "4" in reply


def test_ai_test_route_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post("/api/ai/test")

    assert response.status_code == 401


def test_ai_test_route_returns_502_on_openrouter_error() -> None:
    client = TestClient(app)
    client.post("/api/login", json=VALID_CREDENTIALS)

    with patch("app.main.complete", side_effect=OpenRouterError("boom")):
        response = client.post("/api/ai/test")

    assert response.status_code == 502
