# Code Review

Date: 2026-08-10
Scope: full repository (`backend/`, `frontend/`, Docker/deploy config), as of the current working tree (no commits yet in this repo).

## Summary

This is a small, well-scoped Kanban MVP (FastAPI + SQLite backend, Next.js static-export frontend, single hardcoded user, AI chat that can edit the board via OpenRouter). Overall quality is high for an MVP: clear separation of concerns (`auth.py` / `db.py` / `board.py` / `ai.py` / `chat.py`), decent test coverage on the backend (auth, board CRUD, chat, static routing, AI error paths) and reasonable frontend test coverage (unit + Playwright e2e). `docs/PLAN.md` and `docs/DATABASE.md` show that several things that might otherwise look like bugs (hardcoded auth, in-memory sessions, unused `users.password` column) are **deliberate, documented MVP simplifications** — those are not re-flagged as findings below.

Only one finding rises above "low": the Docker healthcheck is likely broken because `curl` probably isn't installed in the final image.

## Findings

### 1. ~~Docker healthcheck likely always fails~~ — FIXED

`docker-compose.yml` ran `CMD ["curl", "-f", "http://localhost:8000/api/health"]` inside the container, but the final stage's base image, `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, does not install `curl` (the Dockerfile never runs `apt-get install`). Debian slim images don't ship `curl` by default, so the healthcheck command would most likely have failed with "executable file not found," making the container permanently report `unhealthy` even though the app is running fine.

- `docker-compose.yml:11-16`, `Dockerfile:11-26`
- `docs/PLAN.md` documents curling the app from the **host** (`curl http://localhost:8000/...`) as verification, which is a different thing from the in-container `HEALTHCHECK`.
- **Fix applied**: swapped the healthcheck to `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"`, which uses the Python already present in the image instead of an uninstalled `curl`. **Verified** via `docker compose up --build`: `docker compose ps` / `docker inspect` show `STATUS: healthy` once the app is up (the one check during the `start_period` before uvicorn is listening fails with connection-refused as expected and doesn't count against the retry budget).

### 2. Card title can be blanked out with no server-side validation

`CreateCardRequest.title` requires `min_length=1` (`backend/app/main.py:111`), but `UpdateCardRequest.title` has no such constraint (`backend/app/main.py:116`) and `Card`/`Column` in `board.py` place no constraints on `title` either. Two consequences:

- `PATCH /api/cards/{id}` with `{"title": ""}` succeeds and blanks the card's title. The UI never sends this today, but the API allows it.
- The AI chat's `board_update` JSON schema (`backend/app/chat.py:24-64`) also has no `minLength` on `title`, so a model response with an empty title would pass `_validate_board_update` and get written to the board.
- Suggested fix: add `Field(min_length=1)` to `UpdateCardRequest.title`/`RenameColumnRequest` is already fine, and add `"minLength": 1` to the `title` fields in `RESPONSE_SCHEMA`.

### 3. `ChatSidebar` doesn't handle session expiry the way the rest of the app does

`KanbanBoard` routes every API failure through `handleApiError`, which specifically checks for `UnauthorizedError` and calls `onUnauthorized` to redirect to `/login` (`frontend/src/components/KanbanBoard.tsx:70-77`). `ChatSidebar.handleSubmit` calls `api.sendChatMessage` directly and catches everything generically as "Something went wrong sending that message" (`frontend/src/components/ChatSidebar.tsx:46-54`), without distinguishing a `401`/expired session. If the session cookie is gone (server restart clears in-memory sessions, or manual logout in another tab), the chat just shows a generic error instead of sending the user to `/login` like every other board action does. No test covers this path either (`ChatSidebar.test.tsx` has no 401 case).

- Suggested fix: thread `onUnauthorized` (or reuse `handleApiError`) into `ChatSidebar`, same as `KanbanBoard`.

### 4. `replace_board` isn't transactionally safe against partial failure

`add_card` wraps its read-modify-write in `BEGIN IMMEDIATE` / `commit` / `rollback` (`backend/app/board.py:85-100`), but `replace_board` — used for every AI-driven board update — does a bare `DELETE` followed by a loop of `INSERT`s and a single `commit()` at the end with no `try`/`except`/`rollback` (`backend/app/board.py:184-206`). If an exception is raised partway through the insert loop (e.g. a future schema constraint violation), the columns for the board would already be deleted with no rollback, leaving the board empty. Low likelihood today since `_validate_board_update` pre-validates shape, but the inconsistency with `add_card`'s pattern is worth closing.

### 5. Stale/incorrect statement in `docs/PLAN.md` about the env file being optional

`docs/PLAN.md:25` says "`docker-compose.yml` treats it as optional so the container still starts without it," but the current `docker-compose.yml:6-8` sets `env_file: { path: .env, required: true }` — `docker compose up` will now fail outright if `.env` is missing, contradicting the doc. Not a code bug (a `.env` is present in this checkout), but worth fixing the doc or reverting the compose file to match the documented intent, since a new contributor following the doc's "just skip `.env`" claim will hit a hard failure.

### 6. Per-session chat history grows unbounded

`_HISTORY` in `backend/app/chat.py:11` accumulates every user/assistant turn for the lifetime of a session with no cap or truncation, and the full history plus the full board JSON is sent to OpenRouter on every `/api/chat` call (`backend/app/chat.py:87-97`). For a short-lived local MVP session this is fine, but a long chat session will make each request slower and more expensive, and could eventually exceed the model's context window. Worth a note for whenever this moves past MVP (e.g. cap history length, or summarize older turns).

### 7. No CI

There's no `.github/workflows` (or equivalent) running `pytest` / `npm run test:all` / lint on push. Given the project already has solid test suites on both sides, wiring them into CI would be low effort and catch regressions before they reach `main`.

## Nice to have / not blocking

- The final image's base tag (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`) isn't digest-pinned, so a rebuild months from now could pick up a different `uv`/Python patch version silently. Fine for an MVP; consider pinning by digest if reproducibility matters later.
- `frontend/src/components/KanbanBoard.tsx:125` generates optimistic temp card ids from `Date.now()`; two adds within the same millisecond (not realistically reachable via the UI's own click-to-open-form flow) would collide. Not worth changing given `NewCardForm` can't produce that in practice.

## Strengths worth keeping

- Backend tests are thorough and test the *right* things: auth boundaries on every route, 404s on all not-found paths, AI-failure paths (`OpenRouterError` → 502), and a real "board update gets rejected if malformed" contract (`test_chat.py`, `chat.py`'s `_validate_board_update`).
- `NextStaticFiles` (`backend/app/main.py:43-58`) and its dedicated test file solve a genuinely subtle Next.js static-export routing gotcha, with a clear docstring explaining *why*.
- Frontend keeps optimistic UI updates simple and self-healing: on any API error the board just refetches from the server (`handleApiError` in `KanbanBoard.tsx`), rather than hand-rolling rollback logic per action.
- `docs/PLAN.md` and `docs/DATABASE.md` clearly record *why* certain shortcuts were taken (hardcoded auth, in-memory sessions, unused `users.password`), which made this review far easier — most "looks like a bug" candidates turned out to be documented, intentional MVP tradeoffs.
