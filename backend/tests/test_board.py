from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app

VALID_CREDENTIALS = {"username": "user", "password": "password"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        test_client.post("/api/login", json=VALID_CREDENTIALS)
        yield test_client


def test_get_board_returns_seeded_data(client: TestClient) -> None:
    response = client.get("/api/board")

    assert response.status_code == 200
    body = response.json()
    assert len(body["columns"]) == 5
    assert body["columns"][0]["id"] == "col-backlog"
    assert body["columns"][0]["cardIds"] == ["card-1", "card-2"]
    assert body["cards"]["card-1"]["title"] == "Align roadmap themes"


def test_get_board_requires_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get("/api/board")

    assert response.status_code == 401


def test_rename_column(client: TestClient) -> None:
    response = client.patch("/api/columns/col-backlog", json={"title": "Triage"})

    assert response.status_code == 200
    assert response.json()["columns"][0]["title"] == "Triage"


def test_rename_unknown_column_is_404(client: TestClient) -> None:
    response = client.patch("/api/columns/does-not-exist", json={"title": "Triage"})

    assert response.status_code == 404


def test_create_card_appends_to_column(client: TestClient) -> None:
    response = client.post(
        "/api/cards", json={"column_id": "col-backlog", "title": "New card", "details": "Some notes"}
    )

    assert response.status_code == 200
    body = response.json()
    backlog = next(column for column in body["columns"] if column["id"] == "col-backlog")
    new_card_id = backlog["cardIds"][-1]
    assert body["cards"][new_card_id]["title"] == "New card"
    assert body["cards"][new_card_id]["details"] == "Some notes"


def test_create_card_in_unknown_column_is_404(client: TestClient) -> None:
    response = client.post("/api/cards", json={"column_id": "does-not-exist", "title": "x", "details": ""})

    assert response.status_code == 404


def test_update_card_fields(client: TestClient) -> None:
    response = client.patch(
        "/api/cards/card-1", json={"title": "Updated title", "details": "Updated details"}
    )

    assert response.status_code == 200
    assert response.json()["cards"]["card-1"]["title"] == "Updated title"
    assert response.json()["cards"]["card-1"]["details"] == "Updated details"


def test_update_unknown_card_is_404(client: TestClient) -> None:
    response = client.patch("/api/cards/does-not-exist", json={"title": "x"})

    assert response.status_code == 404


def test_move_card_to_another_column(client: TestClient) -> None:
    response = client.patch("/api/cards/card-1", json={"column_id": "col-done"})

    assert response.status_code == 200
    body = response.json()
    backlog = next(column for column in body["columns"] if column["id"] == "col-backlog")
    done = next(column for column in body["columns"] if column["id"] == "col-done")
    assert "card-1" not in backlog["cardIds"]
    assert done["cardIds"][-1] == "card-1"


def test_move_card_to_specific_position_within_column(client: TestClient) -> None:
    # col-backlog starts as [card-1, card-2]; move card-2 to position 0.
    response = client.patch("/api/cards/card-2", json={"column_id": "col-backlog", "position": 0})

    assert response.status_code == 200
    backlog = next(column for column in response.json()["columns"] if column["id"] == "col-backlog")
    assert backlog["cardIds"] == ["card-2", "card-1"]


def test_move_card_to_unknown_column_is_404(client: TestClient) -> None:
    response = client.patch("/api/cards/card-1", json={"column_id": "does-not-exist"})

    assert response.status_code == 404


def test_delete_card(client: TestClient) -> None:
    response = client.delete("/api/cards/card-1")

    assert response.status_code == 200
    body = response.json()
    assert "card-1" not in body["cards"]
    backlog = next(column for column in body["columns"] if column["id"] == "col-backlog")
    assert "card-1" not in backlog["cardIds"]


def test_delete_unknown_card_is_404(client: TestClient) -> None:
    response = client.delete("/api/cards/does-not-exist")

    assert response.status_code == 404


def test_board_persists_across_reconnects_to_the_same_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "persist.db"))

    with TestClient(app) as first_client:
        first_client.post("/api/login", json=VALID_CREDENTIALS)
        first_client.post(
            "/api/cards", json={"column_id": "col-backlog", "title": "Persisted card", "details": ""}
        )

    with TestClient(app) as second_client:
        second_client.post("/api/login", json=VALID_CREDENTIALS)
        response = second_client.get("/api/board")

    titles = [card["title"] for card in response.json()["cards"].values()]
    assert "Persisted card" in titles
