"""MCP server exposing the PM board as tools for Claude.

Talks to the SQLite board storage directly (reusing app.board), bypassing
the FastAPI HTTP layer entirely — there's no multi-user auth to satisfy
for a single local board, so going through the session-cookie flow would
be pure overhead. Run locally via stdio; see README.md for setup.
"""

import os
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from app.board import (
    BoardNotFound,
    CardNotFound,
    ColumnNotFound,
    add_card,
    delete_card as delete_card_row,
    get_board as get_board_row,
    rename_column as rename_column_row,
    update_card as update_card_row,
)
from app.db import get_connection, init_db

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pm.db"

mcp = FastMCP(
    name="pm-board",
    instructions=(
        "Tools for reading and editing a personal kanban board (columns and cards). "
        "Call get_board first to see current column and card IDs before creating, "
        "moving, or deleting cards."
    ),
)


def _db_path() -> Path:
    override = os.environ.get("DATABASE_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


@mcp.tool(annotations={"readOnlyHint": True, "title": "Get board"})
def get_board_tool() -> dict:
    """Fetch the full board: all columns in order, and all cards keyed by ID.

    Call this first — you need column IDs and card IDs before calling any
    other tool.
    """
    conn = get_connection(_db_path())
    try:
        init_db(conn)
        try:
            board = get_board(conn)
        except BoardNotFound:
            return {"columns": [], "cards": {}}
        return board.model_dump()
    finally:
        conn.close()


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "title": "Create card"})
def create_card(
    column_id: Annotated[str, Field(description="ID of the column to add the card to, from get_board.")],
    title: Annotated[str, Field(description="Card title.", min_length=1)],
    details: Annotated[str, Field(description="Card body/description. Defaults to empty.")] = "",
) -> dict:
    """Create a new card at the end of the given column. Returns the new card's ID."""
    conn = get_connection(_db_path())
    try:
        try:
            card_id = add_card(conn, column_id, title, details)
        except ColumnNotFound:
            return {"error": f"Column {column_id!r} not found. Call get_board to see valid column IDs."}
        return {"card_id": card_id}
    finally:
        conn.close()


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "title": "Update card"})
def update_card(
    card_id: Annotated[str, Field(description="ID of the card to update, from get_board.")],
    title: Annotated[str | None, Field(description="New title. Omit to leave unchanged.")] = None,
    details: Annotated[str | None, Field(description="New body/description. Omit to leave unchanged.")] = None,
    column_id: Annotated[
        str | None, Field(description="Move the card to this column ID. Omit to leave in its current column.")
    ] = None,
    position: Annotated[
        int | None, Field(description="0-based position within the target column. Omit to append at the end.")
    ] = None,
) -> dict:
    """Update a card's title, details, and/or move it to a different column/position."""
    conn = get_connection(_db_path())
    try:
        try:
            update_card_row(conn, card_id, title=title, details=details, column_id=column_id, position=position)
        except CardNotFound:
            return {"error": f"Card {card_id!r} not found. Call get_board to see valid card IDs."}
        except ColumnNotFound:
            return {"error": f"Column {column_id!r} not found. Call get_board to see valid column IDs."}
        return {"status": "ok"}
    finally:
        conn.close()


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "title": "Delete card"})
def delete_card(card_id: Annotated[str, Field(description="ID of the card to delete, from get_board.")]) -> dict:
    """Permanently delete a card. This cannot be undone."""
    conn = get_connection(_db_path())
    try:
        try:
            delete_card_row(conn, card_id)
        except CardNotFound:
            return {"error": f"Card {card_id!r} not found. Call get_board to see valid card IDs."}
        return {"status": "ok"}
    finally:
        conn.close()


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "title": "Rename column"})
def rename_column(
    column_id: Annotated[str, Field(description="ID of the column to rename, from get_board.")],
    title: Annotated[str, Field(description="New column title.", min_length=1)],
) -> dict:
    """Rename a column (e.g. rename 'In Progress' to 'Doing')."""
    conn = get_connection(_db_path())
    try:
        try:
            rename_column_row(conn, column_id, title)
        except ColumnNotFound:
            return {"error": f"Column {column_id!r} not found. Call get_board to see valid column IDs."}
        return {"status": "ok"}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
