import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ai import OpenRouterError, complete
from app.auth import (
    SESSION_COOKIE,
    create_session,
    destroy_session,
    is_valid_session,
    require_session,
    verify_credentials,
)
from app.board import (
    BoardData,
    BoardNotFound,
    CardNotFound,
    ColumnNotFound,
    add_card,
    delete_card,
    get_board,
    rename_column,
    replace_board,
    update_card,
)
from app.chat import (
    InvalidBoardUpdate,
    clear_history,
    get_history,
    parse_board_update,
    request_chat_completion,
)
from app.db import get_connection, get_db, init_db

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class NextStaticFiles(StaticFiles):
    """Resolve paths to their pre-rendered `<path>.html` file first.

    Next.js's static export writes one HTML file per route (e.g. `login.html`
    for `/login`) *and* a same-named directory of RSC prefetch data (`login/`,
    with no `index.html` inside). Plain StaticFiles matches that directory
    first and then 404s, since it never finds an `index.html` inside it. Try
    `<path>.html` before the raw path so the actual page wins.
    """

    def lookup_path(self, path: str) -> tuple[str, object]:
        if path not in ("", "."):
            full_path, stat_result = super().lookup_path(f"{path}.html")
            if stat_result is not None:
                return full_path, stat_result
        return super().lookup_path(path)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn = get_connection()
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="pm-backend", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class Credentials(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(credentials: Credentials, response: Response) -> dict[str, str]:
    if not verify_credentials(credentials.username, credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    response.set_cookie(SESSION_COOKIE, create_session(), httponly=True, samesite="lax")
    return {"status": "ok"}


@app.post("/api/logout")
def logout(response: Response, session_id: Annotated[str | None, Cookie()] = None) -> dict[str, str]:
    destroy_session(session_id)
    clear_history(session_id)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/session")
def session_status(session_id: Annotated[str | None, Cookie()] = None) -> dict[str, bool]:
    return {"authenticated": is_valid_session(session_id)}


class RenameColumnRequest(BaseModel):
    title: str = Field(min_length=1)


class CreateCardRequest(BaseModel):
    column_id: str
    title: str = Field(min_length=1)
    details: str = ""


class UpdateCardRequest(BaseModel):
    title: str | None = None
    details: str | None = None
    column_id: str | None = None
    position: int | None = None


@app.get("/api/board", dependencies=[Depends(require_session)])
def read_board(conn: sqlite3.Connection = Depends(get_db)) -> BoardData:
    try:
        return get_board(conn)
    except BoardNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


@app.patch("/api/columns/{column_id}", dependencies=[Depends(require_session)])
def rename_column_route(
    column_id: str, payload: RenameColumnRequest, conn: sqlite3.Connection = Depends(get_db)
) -> BoardData:
    try:
        rename_column(conn, column_id, payload.title)
    except ColumnNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    return get_board(conn)


@app.post("/api/cards", dependencies=[Depends(require_session)])
def create_card_route(payload: CreateCardRequest, conn: sqlite3.Connection = Depends(get_db)) -> BoardData:
    try:
        add_card(conn, payload.column_id, payload.title, payload.details)
    except ColumnNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    return get_board(conn)


@app.patch("/api/cards/{card_id}", dependencies=[Depends(require_session)])
def update_card_route(
    card_id: str, payload: UpdateCardRequest, conn: sqlite3.Connection = Depends(get_db)
) -> BoardData:
    try:
        update_card(
            conn,
            card_id,
            title=payload.title,
            details=payload.details,
            column_id=payload.column_id,
            position=payload.position,
        )
    except CardNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    except ColumnNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    return get_board(conn)


@app.delete("/api/cards/{card_id}", dependencies=[Depends(require_session)])
def delete_card_route(card_id: str, conn: sqlite3.Connection = Depends(get_db)) -> BoardData:
    try:
        delete_card(conn, card_id)
    except CardNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return get_board(conn)


class AiTestResponse(BaseModel):
    reply: str


@app.post("/api/ai/test", dependencies=[Depends(require_session)])
def ai_test_route() -> AiTestResponse:
    try:
        reply = complete([{"role": "user", "content": "What is 2+2? Answer with just the number."}])
    except OpenRouterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return AiTestResponse(reply=reply)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    board: BoardData


@app.post("/api/chat", dependencies=[Depends(require_session)])
def chat_route(
    payload: ChatRequest,
    conn: sqlite3.Connection = Depends(get_db),
    session_id: str = Depends(require_session),
) -> ChatResponse:
    board = get_board(conn)
    history = get_history(session_id)

    try:
        raw = request_chat_completion(board, history, payload.message)
    except OpenRouterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    reply = raw.get("reply", "")

    try:
        board_update = parse_board_update(raw.get("board_update"))
    except InvalidBoardUpdate:
        # Reject rather than risk corrupting the board with a malformed update.
        board_update = None

    if board_update is not None:
        replace_board(conn, board_update)
        board = get_board(conn)

    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": reply})

    return ChatResponse(reply=reply, board=board)


app.mount("/", NextStaticFiles(directory=STATIC_DIR, html=True), name="static")
