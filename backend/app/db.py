import os
import sqlite3
from pathlib import Path
from typing import Iterator

from app.auth import PASSWORD, USERNAME

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS columns (
    id TEXT PRIMARY KEY,
    board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_columns_board_position ON columns(board_id, position);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    column_id TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_column_position ON cards(column_id, position);
"""

INITIAL_COLUMNS = [
    ("col-backlog", "Backlog"),
    ("col-discovery", "Discovery"),
    ("col-progress", "In Progress"),
    ("col-review", "Review"),
    ("col-done", "Done"),
]

INITIAL_CARDS: dict[str, list[tuple[str, str, str]]] = {
    "col-backlog": [
        ("card-1", "Align roadmap themes", "Draft quarterly themes with impact statements and metrics."),
        ("card-2", "Gather customer signals", "Review support tags, sales notes, and churn feedback."),
    ],
    "col-discovery": [
        ("card-3", "Prototype analytics view", "Sketch initial dashboard layout and key drill-downs."),
    ],
    "col-progress": [
        ("card-4", "Refine status language", "Standardize column labels and tone across the board."),
        ("card-5", "Design card layout", "Add hierarchy and spacing for scanning dense lists."),
    ],
    "col-review": [
        ("card-6", "QA micro-interactions", "Verify hover, focus, and loading states."),
    ],
    "col-done": [
        ("card-7", "Ship marketing page", "Final copy approved and asset pack delivered."),
        ("card-8", "Close onboarding sprint", "Document release notes and share internally."),
    ],
}


def _database_path() -> Path:
    # Read lazily (not at import time) so tests can point this at a temp file.
    return Path(os.environ.get("DATABASE_PATH", "data/pm.db"))


def get_connection(path: Path | str | None = None) -> sqlite3.Connection:
    resolved_path = Path(path) if path is not None else _database_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _seed_if_empty(conn)


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    user = conn.execute("SELECT id FROM users WHERE username = ?", (USERNAME,)).fetchone()
    if user is None:
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (USERNAME, PASSWORD))
        user = conn.execute("SELECT id FROM users WHERE username = ?", (USERNAME,)).fetchone()
    user_id = user["id"]

    board = conn.execute("SELECT id FROM boards WHERE user_id = ?", (user_id,)).fetchone()
    if board is None:
        cursor = conn.execute("INSERT INTO boards (user_id) VALUES (?)", (user_id,))
        board_id = cursor.lastrowid
        for position, (column_id, title) in enumerate(INITIAL_COLUMNS):
            conn.execute(
                "INSERT INTO columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
                (column_id, board_id, title, position),
            )
            for card_position, (card_id, card_title, details) in enumerate(INITIAL_CARDS[column_id]):
                conn.execute(
                    "INSERT INTO cards (id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?)",
                    (card_id, column_id, card_title, details, card_position),
                )

    conn.commit()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
