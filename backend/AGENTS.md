# Backend

FastAPI backend, managed with `uv`. Serves the API and (from Part 3 onward) the built frontend.

## Structure

```text
app/
  main.py          FastAPI app; lifespan runs db.init_db(); NextStaticFiles mount; all routes
  auth.py          Hardcoded credential check, in-memory session store, require_session dependency
  db.py            SQLite schema (DDL), seeding from the frontend's initialData, get_db per-request dependency
  board.py          BoardData/Column/Card pydantic models + CRUD functions operating on a sqlite3.Connection
  ai.py             OpenRouter client (complete/complete_structured); loads root .env locally, reads OPENROUTER_API_KEY
  chat.py            /api/chat's logic: system prompt, response JSON schema, per-session history, board_update parsing/validation
static/             Static files served at "/" (placeholder index.html until Part 3 replaces it with the built frontend)
tests/
  test_health.py         pytest + FastAPI TestClient
  test_static_routing.py  NextStaticFiles path resolution, incl. the login.html/login/ directory collision
  test_auth.py            login/logout/session routes, require_session dependency
  test_board.py            board CRUD routes, incl. persistence across a fresh connection to the same db file
  test_ai.py                OpenRouter client error handling (mocked httpx) + one real call, skipped if no API key
  test_chat.py               board_update validation, /api/chat route (mocked OpenRouter call) + 2 real-call tests, skipped if no API key
```

## Conventions

- Routes live under `/api/*`; everything else falls through to `NextStaticFiles` (mounted last, `html=True`) so `/` serves `static/index.html` and other routes resolve to their pre-rendered `<path>.html` — see the class docstring in `main.py` for why a plain `StaticFiles` isn't enough (Next 16's static export writes a same-named directory alongside each route's HTML file).
- Auth (`auth.py`): single hardcoded user (`user`/`password`), session tokens are random strings held in an in-memory `set` — cleared on process restart, which is fine for this MVP. `require_session` gates the board routes via `dependencies=[Depends(require_session)]`. The session cookie is HttpOnly; static/page serving is intentionally *not* gated server-side (static export has no per-request logic) — the frontend's `AuthGate` component checks `/api/session` and redirects client-side instead.
- Database (`db.py`): SQLite file at `DATABASE_PATH` env var (default `data/pm.db`, relative to cwd — resolves to `/app/data/pm.db` in Docker, matching the `db-data` volume in `docker-compose.yml`; resolves to `backend/data/pm.db` for local dev, gitignored). Schema/seed run once per process via `init_db()` in `main.py`'s `lifespan`. Read the path lazily (not a module-level constant) so tests can point `DATABASE_PATH` at a `tmp_path` file before the app's lifespan runs. `get_db()` opens and closes a fresh connection per request — simplest correct approach for SQLite, no shared-connection threading concerns.
- Board (`board.py`): `users`/`boards` tables exist for the FK relationship and future multi-user support, but auth and board lookup don't use them for identity — see `docs/DATABASE.md` and `_get_board_id`'s comment. Every mutating function takes a `sqlite3.Connection` and commits internally; routes in `main.py` catch `ColumnNotFound`/`CardNotFound`/`BoardNotFound` and turn them into 404s.
- AI (`ai.py`): `complete(messages)` and `complete_structured(messages, schema_name, schema)` both POST to OpenRouter (`openai/gpt-oss-120b`) via a shared `_post_chat_completion`/`_extract_content` pair — `complete_structured` adds a `response_format: {type: "json_schema", json_schema: {strict: true, ...}}` for Part 9's chat route. Both raise `OpenRouterError` for a missing key, network failure, non-200, or an unexpected response shape — routes map that to a 502. `load_dotenv()` runs at import time pointed at the repo-root `.env` (`parents[2]` from `app/ai.py`) since local `uv run` has `cwd=backend/`; in Docker, `OPENROUTER_API_KEY` is already injected via `docker-compose.yml`'s `env_file`, so the (absent) `.env` load there is just a no-op.
- Chat (`chat.py`): `/api/chat` always sends the current board (as JSON, `cards` as an **array** — see below) plus per-session history plus the new message, requesting structured output matching `RESPONSE_SCHEMA` (`{reply, board_update}`). `board_update`, if present, is a **full-board replacement** (not a diff/patch) — `parse_board_update` converts its array-of-cards wire shape into the internal dict-keyed `BoardData`, then `_validate_board_update` checks internal consistency (unique column ids, each card referenced by exactly one column, no dangling/orphaned ids) before `board.py`'s `replace_board` (delete-and-reinsert) persists it. An invalid `board_update` is silently ignored — the reply still comes back, the board just doesn't change. `cards` must be an array in the wire schema (not the dict-by-id shape used elsewhere) because strict-mode JSON Schema structured outputs don't support a dynamic-keyed object. Conversation history lives in an in-memory `dict[session_id, list[message]]`, cleared on logout — same "in-memory is fine for this MVP" call as sessions themselves (Part 5).
- Dependencies split into runtime (`dependencies`) and dev-only (`dependency-groups.dev`, currently just `pytest`) in `pyproject.toml`. `httpx` is a runtime dependency (used by both `ai.py` and `TestClient`), not dev-only, despite mostly showing up in tests.
- Run locally: `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`.
- The Docker image (root `Dockerfile`) installs deps with `uv sync --locked --no-dev` — keep `uv.lock` committed and up to date via `uv add`/`uv remove`, not manual edits.
- For local e2e testing, `frontend/playwright.config.ts` runs this backend on port 8000 (`uv run --directory ../backend uvicorn ...`) alongside `next dev` on port 3000, which proxies `/api/*` to it (see `frontend/next.config.ts`).
- Tests that hit the database must use `with TestClient(app) as client:` (not a bare `TestClient(app)`) — only the context-manager form runs the FastAPI `lifespan`, which is what creates/seeds the SQLite schema. Tests that don't touch the DB (health/auth/static routing) intentionally use the bare form so they don't trigger it.

See [../docs/PLAN.md](../docs/PLAN.md) for what's implemented per part and [../docs/DATABASE.md](../docs/DATABASE.md) for the schema.
