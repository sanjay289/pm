# Database

SQLite, created on first backend startup if the file doesn't exist (per [../AGENTS.md](../AGENTS.md)). Schema: [schema.json](schema.json).

## Shape

Four tables, mirroring the frontend's normalized `BoardData` type ([../frontend/src/lib/kanban.ts](../frontend/src/lib/kanban.ts)) directly rather than introducing a different in-DB representation:

```text
users (id, username, password)
  └─ boards (id, user_id UNIQUE)         -- UNIQUE enforces "1 board per user" for the MVP
       └─ columns (id, board_id, title, position)
            └─ cards (id, column_id, title, details, position)
```

- `columns.id` / `cards.id` are `TEXT`, using the same string ids the frontend already generates (`col-backlog`, `card-1`, ids from `createId()`), so the API layer can pass ids straight through without an int↔string mapping.
- `users.id` / `boards.id` are `INTEGER AUTOINCREMENT` — internal-only, never sent to the frontend.
- Ordering: the frontend's `Column.cardIds` array (and the board's column order) becomes a `position` integer column, read back with `ORDER BY position`.
- `ON DELETE CASCADE` on both FKs so removing a board/column cleans up its children without the API doing it manually.

## Seeding

On first run: insert the hardcoded user row (`user` / `password`), then a board for that user seeded with the frontend's existing `initialData` (5 columns, 8 cards) so the Part 6 API has something to return immediately.

## Decisions (approved)

1. **The `users.password` column is not used for authentication.** Login keeps checking the hardcoded constants in `backend/app/auth.py`, not the database. The `users` table exists to give `boards` a real foreign-key owner and to model the future multi-user shape `AGENTS.md` calls for, not to drive login.
2. **Sessions stay in-memory, not DB-backed.** No `sessions` table. Session loss on a backend restart is a non-issue for local MVP dev.
