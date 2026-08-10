import os
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.ai import OpenRouterError
from app.chat import InvalidBoardUpdate, parse_board_update
from app.main import app

VALID_CREDENTIALS = {"username": "user", "password": "password"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        test_client.post("/api/login", json=VALID_CREDENTIALS)
        yield test_client


# --- parse_board_update / validation ---


def test_parse_board_update_returns_none_for_none() -> None:
    assert parse_board_update(None) is None


def test_parse_board_update_accepts_a_valid_update() -> None:
    raw = {
        "columns": [{"id": "col-a", "title": "A", "cardIds": ["card-1"]}],
        "cards": [{"id": "card-1", "title": "Card 1", "details": ""}],
    }

    board = parse_board_update(raw)

    assert board is not None
    assert board.columns[0].id == "col-a"
    assert board.cards["card-1"].title == "Card 1"


def test_parse_board_update_rejects_malformed_shape() -> None:
    with pytest.raises(InvalidBoardUpdate):
        parse_board_update({"columns": [{"id": "col-a"}], "cards": []})


def test_parse_board_update_rejects_duplicate_column_ids() -> None:
    raw = {
        "columns": [
            {"id": "col-a", "title": "A", "cardIds": []},
            {"id": "col-a", "title": "A again", "cardIds": []},
        ],
        "cards": [],
    }

    with pytest.raises(InvalidBoardUpdate, match="Duplicate column"):
        parse_board_update(raw)


def test_parse_board_update_rejects_card_referenced_by_two_columns() -> None:
    raw = {
        "columns": [
            {"id": "col-a", "title": "A", "cardIds": ["card-1"]},
            {"id": "col-b", "title": "B", "cardIds": ["card-1"]},
        ],
        "cards": [{"id": "card-1", "title": "Card 1", "details": ""}],
    }

    with pytest.raises(InvalidBoardUpdate, match="more than one column"):
        parse_board_update(raw)


def test_parse_board_update_rejects_dangling_card_reference() -> None:
    raw = {"columns": [{"id": "col-a", "title": "A", "cardIds": ["card-missing"]}], "cards": []}

    with pytest.raises(InvalidBoardUpdate, match="disagree"):
        parse_board_update(raw)


def test_parse_board_update_rejects_orphaned_card() -> None:
    raw = {
        "columns": [{"id": "col-a", "title": "A", "cardIds": []}],
        "cards": [{"id": "card-1", "title": "Card 1", "details": ""}],
    }

    with pytest.raises(InvalidBoardUpdate, match="disagree"):
        parse_board_update(raw)


# --- route (mocked OpenRouter call) ---


def test_chat_requires_authentication() -> None:
    response = TestClient(app).post("/api/chat", json={"message": "hi"})

    assert response.status_code == 401


def test_chat_reply_only_leaves_board_unchanged(client: TestClient) -> None:
    board_before = client.get("/api/board").json()

    with patch(
        "app.main.request_chat_completion", return_value={"reply": "Hi there!", "board_update": None}
    ):
        response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hi there!"
    assert body["board"] == board_before


def test_chat_applies_a_valid_board_update(client: TestClient) -> None:
    board_before = client.get("/api/board").json()
    first_column_id = board_before["columns"][0]["id"]
    updated_board = {"columns": [{"id": first_column_id, "title": "Renamed by AI", "cardIds": []}], "cards": []}

    with patch(
        "app.main.request_chat_completion",
        return_value={"reply": "Done!", "board_update": updated_board},
    ):
        response = client.post("/api/chat", json={"message": "rename the first column"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Done!"
    assert body["board"]["columns"] == [{"id": first_column_id, "title": "Renamed by AI", "cardIds": []}]

    board_after = client.get("/api/board").json()
    assert board_after["columns"][0]["title"] == "Renamed by AI"


def test_chat_ignores_an_invalid_board_update(client: TestClient) -> None:
    board_before = client.get("/api/board").json()
    invalid_update = {"columns": [{"id": "col-x", "title": "X", "cardIds": ["card-missing"]}], "cards": []}

    with patch(
        "app.main.request_chat_completion",
        return_value={"reply": "I moved it!", "board_update": invalid_update},
    ):
        response = client.post("/api/chat", json={"message": "do something"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "I moved it!"
    assert body["board"] == board_before


def test_chat_returns_502_on_openrouter_error(client: TestClient) -> None:
    with patch("app.main.request_chat_completion", side_effect=OpenRouterError("boom")):
        response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 502


def test_chat_accumulates_conversation_history(client: TestClient) -> None:
    captured_histories = []

    def fake_request(board, history, message):
        captured_histories.append(list(history))
        return {"reply": f"echo: {message}", "board_update": None}

    with patch("app.main.request_chat_completion", side_effect=fake_request):
        client.post("/api/chat", json={"message": "first"})
        client.post("/api/chat", json={"message": "second"})

    assert captured_histories[0] == []
    assert captured_histories[1] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "echo: first"},
    ]


# --- real OpenRouter integration ---


@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set")
def test_chat_real_question_does_not_change_board(client: TestClient) -> None:
    board_before = client.get("/api/board").json()

    response = client.post(
        "/api/chat", json={"message": "What is this app for? Just answer, don't change anything."}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"]
    assert body["board"] == board_before


@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set")
def test_chat_real_instruction_moves_a_card(client: TestClient) -> None:
    board_before = client.get("/api/board").json()
    first_card_id = next(iter(board_before["cards"]))
    first_card_title = board_before["cards"][first_card_id]["title"]

    response = client.post(
        "/api/chat", json={"message": f'Move the card titled "{first_card_title}" to the Done column.'}
    )

    assert response.status_code == 200
    body = response.json()
    done_column = next(c for c in body["board"]["columns"] if c["title"] == "Done")
    assert first_card_id in done_column["cardIds"]

    board_after = client.get("/api/board").json()
    done_column_after = next(c for c in board_after["columns"] if c["title"] == "Done")
    assert first_card_id in done_column_after["cardIds"]
