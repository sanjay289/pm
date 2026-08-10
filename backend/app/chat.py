import json
from typing import Any

from pydantic import ValidationError

from app.ai import OpenRouterError, complete_structured
from app.board import BoardData, Card, Column

# In-memory, per-session conversation history (Part 5 decided sessions stay
# in-memory too — consistent, and fine for a single hardcoded user).
_HISTORY: dict[str, list[dict[str, str]]] = {}

SYSTEM_PROMPT = (
    "You are an assistant embedded in a single-board Kanban app. You are given the current "
    "board as JSON: columns in display order, each with an ordered list of card ids, plus a "
    "flat list of cards. Respond to the user's message conversationally in `reply`. "
    "If, and only if, the user asks you to create, edit, move, or reorder cards, or rename "
    "columns, set `board_update` to the COMPLETE new board: every column and every card, "
    "including all the ones you didn't change. Never omit an existing card or column the user "
    "didn't ask you to remove. If the user is just asking a question or chatting, set "
    "`board_update` to null and don't change anything."
)

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "board_update": {
            "type": ["object", "null"],
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "cardIds": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "title", "cardIds"],
                        "additionalProperties": False,
                    },
                },
                "cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                        },
                        "required": ["id", "title", "details"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["columns", "cards"],
            "additionalProperties": False,
        },
    },
    "required": ["reply", "board_update"],
    "additionalProperties": False,
}


class InvalidBoardUpdate(Exception):
    pass


def get_history(session_id: str) -> list[dict[str, str]]:
    return _HISTORY.setdefault(session_id, [])


def clear_history(session_id: str | None) -> None:
    if session_id:
        _HISTORY.pop(session_id, None)


def _board_to_prompt_json(board: BoardData) -> dict[str, Any]:
    return {
        "columns": [column.model_dump() for column in board.columns],
        "cards": [card.model_dump() for card in board.cards.values()],
    }


def request_chat_completion(
    board: BoardData, history: list[dict[str, str]], message: str
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current board: {json.dumps(_board_to_prompt_json(board))}"},
        *history,
        {"role": "user", "content": message},
    ]

    content = complete_structured(messages, schema_name="kanban_reply", schema=RESPONSE_SCHEMA)

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise OpenRouterError(f"Model response was not valid JSON: {content}") from exc


def parse_board_update(raw: dict[str, Any] | None) -> BoardData | None:
    if raw is None:
        return None

    try:
        columns = [Column(**column) for column in raw["columns"]]
        cards = {card["id"]: Card(**card) for card in raw["cards"]}
    except (KeyError, TypeError, ValidationError) as exc:
        raise InvalidBoardUpdate(f"Malformed board_update: {exc}") from exc

    board = BoardData(columns=columns, cards=cards)
    _validate_board_update(board)
    return board


def _validate_board_update(board: BoardData) -> None:
    column_ids = [column.id for column in board.columns]
    if len(column_ids) != len(set(column_ids)):
        raise InvalidBoardUpdate("Duplicate column ids in board_update")

    referenced_card_ids: list[str] = []
    for column in board.columns:
        referenced_card_ids.extend(column.cardIds)

    if len(referenced_card_ids) != len(set(referenced_card_ids)):
        raise InvalidBoardUpdate("A card is referenced by more than one column in board_update")

    if set(referenced_card_ids) != set(board.cards.keys()):
        raise InvalidBoardUpdate("board_update's columns and cards disagree about which cards exist")
