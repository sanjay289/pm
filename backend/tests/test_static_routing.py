from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import NextStaticFiles


def make_client(static_dir: Path) -> TestClient:
    app = FastAPI()
    app.mount("/", NextStaticFiles(directory=static_dir, html=True), name="static")
    return TestClient(app)


def test_serves_index_at_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Board</h1>")

    response = make_client(tmp_path).get("/")

    assert response.status_code == 200
    assert "Board" in response.text


def test_resolves_unmatched_path_to_its_prerendered_html_file(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Board</h1>")
    (tmp_path / "login.html").write_text("<h1>Login</h1>")

    response = make_client(tmp_path).get("/login")

    assert response.status_code == 200
    assert "Login" in response.text


def test_html_file_wins_over_a_same_named_directory(tmp_path: Path) -> None:
    """Next's static export writes both `login.html` and a `login/` dir of
    RSC prefetch data (no `index.html` inside) for a route named `login`."""
    (tmp_path / "index.html").write_text("<h1>Board</h1>")
    (tmp_path / "login.html").write_text("<h1>Login</h1>")
    login_dir = tmp_path / "login"
    login_dir.mkdir()
    (login_dir / "__next.login.txt").write_text("rsc data, not a page")

    response = make_client(tmp_path).get("/login")

    assert response.status_code == 200
    assert "Login" in response.text


def test_path_with_no_matching_html_file_is_404(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Board</h1>")

    response = make_client(tmp_path).get("/does-not-exist")

    assert response.status_code == 404
