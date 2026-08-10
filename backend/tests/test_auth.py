from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE, create_session, require_session
from app.main import app

VALID_CREDENTIALS = {"username": "user", "password": "password"}


def test_login_with_correct_credentials_sets_session_cookie() -> None:
    client = TestClient(app)

    response = client.post("/api/login", json=VALID_CREDENTIALS)

    assert response.status_code == 200
    assert SESSION_COOKIE in response.cookies


def test_login_with_incorrect_credentials_is_rejected() -> None:
    client = TestClient(app)

    response = client.post("/api/login", json={"username": "user", "password": "wrong"})

    assert response.status_code == 401
    assert SESSION_COOKIE not in response.cookies


def test_session_persists_across_requests_via_cookie() -> None:
    client = TestClient(app)
    client.post("/api/login", json=VALID_CREDENTIALS)

    response = client.get("/api/session")

    assert response.json() == {"authenticated": True}


def test_session_is_unauthenticated_without_a_cookie() -> None:
    client = TestClient(app)

    response = client.get("/api/session")

    assert response.json() == {"authenticated": False}


def test_logout_invalidates_the_session() -> None:
    client = TestClient(app)
    client.post("/api/login", json=VALID_CREDENTIALS)

    client.post("/api/logout")
    response = client.get("/api/session")

    assert response.json() == {"authenticated": False}


def make_protected_client() -> TestClient:
    protected_app = FastAPI()

    @protected_app.get("/protected")
    def protected(_: None = Depends(require_session)) -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(protected_app)


def test_require_session_rejects_requests_without_a_valid_session() -> None:
    response = make_protected_client().get("/protected")

    assert response.status_code == 401


def test_require_session_allows_requests_with_a_valid_session() -> None:
    client = make_protected_client()
    client.cookies.set(SESSION_COOKIE, create_session())

    response = client.get("/protected")

    assert response.status_code == 200
