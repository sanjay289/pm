import secrets
import sqlite3

from pydantic import BaseModel


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cardIds: list[str]


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]


class BoardNotFound(Exception):
    pass


class ColumnNotFound(Exception):
    pass


class CardNotFound(Exception):
    pass


def create_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def _get_board_id(conn: sqlite3.Connection) -> int:
    # Single-user MVP: there is only ever one board, so no need to resolve it
    # from the session (sessions don't carry a user identity, see auth.py).
    row = conn.execute("SELECT id FROM boards LIMIT 1").fetchone()
    if row is None:
        raise BoardNotFound
    return row["id"]


def get_board(conn: sqlite3.Connection) -> BoardData:
    board_id = _get_board_id(conn)
    column_rows = conn.execute(
        "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position", (board_id,)
    ).fetchall()

    cards: dict[str, Card] = {}
    columns: list[Column] = []
    for column_row in column_rows:
        card_rows = conn.execute(
            "SELECT id, title, details FROM cards WHERE column_id = ? ORDER BY position",
            (column_row["id"],),
        ).fetchall()
        card_ids: list[str] = []
        for card_row in card_rows:
            cards[card_row["id"]] = Card(
                id=card_row["id"], title=card_row["title"], details=card_row["details"]
            )
            card_ids.append(card_row["id"])
        columns.append(Column(id=column_row["id"], title=column_row["title"], cardIds=card_ids))

    return BoardData(columns=columns, cards=cards)


def rename_column(conn: sqlite3.Connection, column_id: str, title: str) -> None:
    cursor = conn.execute("UPDATE columns SET title = ? WHERE id = ?", (title, column_id))
    if cursor.rowcount == 0:
        raise ColumnNotFound
    conn.commit()


def add_card(conn: sqlite3.Connection, column_id: str, title: str, details: str) -> str:
    column = conn.execute("SELECT id FROM columns WHERE id = ?", (column_id,)).fetchone()
    if column is None:
        raise ColumnNotFound

    conn.execute("BEGIN IMMEDIATE")
    try:
        next_position = conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS next_position FROM cards WHERE column_id = ?",
            (column_id,),
        ).fetchone()["next_position"]

        card_id = create_id("card")
        conn.execute(
            "INSERT INTO cards (id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?)",
            (card_id, column_id, title, details, next_position),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return card_id


def update_card(
    conn: sqlite3.Connection,
    card_id: str,
    title: str | None = None,
    details: str | None = None,
    column_id: str | None = None,
    position: int | None = None,
) -> None:
    card = conn.execute("SELECT column_id FROM cards WHERE id = ?", (card_id,)).fetchone()
    if card is None:
        raise CardNotFound

    if title is not None or details is not None:
        fields = []
        values: list[str] = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if details is not None:
            fields.append("details = ?")
            values.append(details)
        values.append(card_id)
        conn.execute(f"UPDATE cards SET {', '.join(fields)} WHERE id = ?", values)

    if column_id is not None or position is not None:
        target_column_id = column_id or card["column_id"]
        target_column = conn.execute(
            "SELECT id FROM columns WHERE id = ?", (target_column_id,)
        ).fetchone()
        if target_column is None:
            raise ColumnNotFound
        _move_card(conn, card_id, card["column_id"], target_column_id, position)

    conn.commit()


def _move_card(
    conn: sqlite3.Connection,
    card_id: str,
    source_column_id: str,
    target_column_id: str,
    position: int | None,
) -> None:
    source_card_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM cards WHERE column_id = ? AND id != ? ORDER BY position",
            (source_column_id, card_id),
        ).fetchall()
    ]

    if source_column_id == target_column_id:
        target_card_ids = source_card_ids
    else:
        target_card_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position", (target_column_id,)
            ).fetchall()
        ]

    insert_at = len(target_card_ids) if position is None else max(0, min(position, len(target_card_ids)))
    target_card_ids.insert(insert_at, card_id)

    conn.execute("UPDATE cards SET column_id = ? WHERE id = ?", (target_column_id, card_id))
    for index, target_card_id in enumerate(target_card_ids):
        conn.execute("UPDATE cards SET position = ? WHERE id = ?", (index, target_card_id))

    if source_column_id != target_column_id:
        for index, source_card_id in enumerate(source_card_ids):
            conn.execute("UPDATE cards SET position = ? WHERE id = ?", (index, source_card_id))


def delete_card(conn: sqlite3.Connection, card_id: str) -> None:
    cursor = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    if cursor.rowcount == 0:
        raise CardNotFound
    conn.commit()


def replace_board(conn: sqlite3.Connection, board: BoardData) -> None:
    """Replace the entire board with `board` (AI chat updates, Part 9).

    Deletes all existing columns (cascading to their cards) and re-inserts
    from scratch. Simpler and just as correct as diffing against current
    state, at this scale (a handful of columns/cards).
    """
    board_id = _get_board_id(conn)
    conn.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))

    for position, column in enumerate(board.columns):
        conn.execute(
            "INSERT INTO columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
            (column.id, board_id, column.title, position),
        )
        for card_position, card_id in enumerate(column.cardIds):
            card = board.cards[card_id]
            conn.execute(
                "INSERT INTO cards (id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?)",
                (card.id, column.id, card.title, card.details, card_position),
            )

    conn.commit()
