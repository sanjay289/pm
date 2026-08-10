# High level steps for project

See [../AGENTS.md](../AGENTS.md) for business requirements, technical decisions, and coding standards. See [../frontend/AGENTS.md](../frontend/AGENTS.md) for the existing frontend code.

Work through parts in order. Each part ends with the checkboxes ticked, its tests passing, and (where noted) explicit user sign-off before moving to the next part.

## Part 1: Plan

- [x] Enrich this document with substeps, tests, and success criteria per part
- [x] Create `frontend/AGENTS.md` describing the existing frontend code
- [ ] User reviews and approves this plan

**Success criteria:** user has explicitly approved this plan before Part 2 starts.

## Part 2: Scaffolding

Set up Docker infrastructure, the FastAPI backend, and start/stop scripts. Prove the container runs, serves a static "hello world" page, and answers an API call.

- [x] `backend/pyproject.toml` set up for `uv`, FastAPI + uvicorn as dependencies
- [x] `backend/app/main.py`: FastAPI app with a `GET /api/health` route returning `{"status": "ok"}`
- [x] `backend/app/main.py`: mount a `static/` directory at `/` (placeholder `index.html` with "Hello world" for now — real frontend build comes in Part 3)
- [x] `Dockerfile` at project root: multi-stage or single-stage build using `uv` to install backend deps, copies a `static/` placeholder, runs uvicorn on container start
- [x] `docker-compose.yml` (or plain `docker run` documented in scripts) exposing the app port, mounting a volume for the SQLite db file so data persists across container restarts
- [x] `scripts/start.sh`, `scripts/stop.sh` (Mac/Linux) and `scripts/start.ps1`, `scripts/stop.ps1` (Windows/PowerShell) that build/run and stop the container
- [x] `.env.example` documenting `OPENROUTER_API_KEY` (root `.env` does not exist yet in this checkout — copy `.env.example` to `.env` and fill in the key; `docker-compose.yml` treats it as optional so the container still starts without it)
- [x] `.gitignore` covers `.env`, `__pycache__`, `.venv`, `node_modules`, `*.db`, `.next`, docker build artifacts

**Tests / verification:**

- `scripts/start.sh` (or `.ps1`) brings the container up; `curl http://localhost:8000/` returns the placeholder HTML page — verified
- `curl http://localhost:8000/api/health` returns `{"status": "ok"}` with HTTP 200 — verified
- `scripts/stop.sh` cleanly stops the container — verified
- `uv run pytest` in `backend/` (2 tests: health route, root page) — verified

**Success criteria:** a fresh clone + `.env` with a valid key + running the start script serves both the hello-world page and a working health-check API call, entirely inside Docker. Met, except no valid `OPENROUTER_API_KEY` was available to test with — the key isn't needed until Part 8, so this doesn't block Part 2.

## Part 3: Add in Frontend

Statically build the existing Next.js frontend and serve it from FastAPI at `/`, replacing the placeholder page. Comprehensive unit and integration tests.

- [x] Configure Next.js for static export (`output: "export"` in `next.config.ts`) since FastAPI serves static files, not a Node server
- [x] Update `Dockerfile` to a multi-stage build: Node stage runs `npm run build` (static export) into `frontend/out`, copied into the backend's static directory in the final Python stage
- [x] FastAPI serves the built frontend at `/` (and its assets); unmatched paths resolve to their pre-rendered `<path>.html` file (`NextStaticFiles` in `backend/app/main.py`) — more precise than a blind index.html fallback, since Next's static export pre-renders each route (e.g. `/login`) to its own HTML file rather than one SPA shell
- [x] `scripts/start.sh`/`.ps1` rebuild the Docker image so frontend changes are picked up (already true via `docker compose up --build`)
- [x] Existing frontend unit tests (`npm run test:unit`) and e2e tests (`npm run test:e2e`) still pass — verified against `next dev` (Playwright's existing config), and separately against the real static export by curling the running Docker container
- [x] Add a backend test asserting static routing behavior, incl. serving prerendered pages by path (`backend/tests/test_static_routing.py`, exercising `NextStaticFiles` directly with a temp directory rather than depending on a real frontend build being present for `pytest` to run)

**Tests / verification:**

- `npm run test:all` in `frontend/` passes unchanged — verified (6 unit tests, 3 e2e tests)
- Backend: 5 pytest tests pass, including the new static-routing tests — verified
- Manual: `docker compose up --build`, `curl http://localhost:8000/` returns the real "Kanban Studio" board HTML (not the Part 2 placeholder), `curl http://localhost:8000/api/health` still OK — verified

**Success criteria:** the Kanban demo is served from the Dockerized backend at `/`, indistinguishable in behavior from running `npm run dev` directly, with all existing frontend tests green. Met.

## Part 4: Add in a fake user sign in experience

Gate `/` behind a hardcoded login (`user` / `password`); support logout. Comprehensive tests.

- [x] Backend: `POST /api/login` accepts `{username, password}`, checks against hardcoded `user`/`password`, on success sets an HttpOnly session cookie (`backend/app/auth.py`: random token via `secrets.token_urlsafe`, stored server-side in-memory in a module-level set — will move to the SQLite db in Part 6 if needed, but an in-memory session is fine for a single hardcoded user)
- [x] Backend: `POST /api/logout` clears the session
- [x] Backend: `GET /api/session` returns whether the current request is authenticated
- [x] Backend: static file serving for `/` and other app routes does not require a session (unauthenticated requests still get the SPA shell; `AuthGate` on the frontend handles the redirect client-side, since static export has no per-request server logic); a reusable `require_session` dependency exists in `auth.py` for Part 6's board routes to enforce 401 when unauthenticated
- [x] Frontend: `/login` route with a simple form (username, password, submit button styled with the existing color tokens), calls `POST /api/login`, redirects to `/` on success, shows an error on failure
- [x] Frontend: on load, `/` (`AuthGate`) checks `GET /api/session`; if unauthenticated, redirect to `/login`
- [x] Frontend: a logout control in the board header that calls `POST /api/logout` and redirects to `/login`

**Tests / verification:**

- Backend: 13 pytest tests (up from 5) — login with correct/incorrect credentials, session persists across requests via cookie, logout invalidates the session, `require_session` dependency rejects/allows correctly — verified
- Frontend unit tests: `src/lib/auth.test.ts`, `src/app/login/page.test.tsx`, `src/components/AuthGate.test.tsx` (mocked `fetch`/`next/navigation`) — 15 tests total, verified
- Playwright e2e (`tests/auth.spec.ts`): logged-out redirect to `/login`, correct-credentials login reaches the board, wrong credentials show an error and stay on `/login`, logout returns to `/login` and blocks board access again — all verified against the real Docker container
- `tests/kanban.spec.ts` updated to log in via `page.request.post("/api/login", ...)` in a `beforeEach` (the board is now gated) — still passing
- Manual: full login → session → logout → session curl sequence against the running container — verified

**Success criteria:** the Kanban board is unreachable without logging in with the hardcoded credentials, and logout fully revokes access, verified end-to-end by Playwright. Met.

**Notable fixes/decisions made along the way:**

- **Static export + `/api/*` don't mix in `next dev`.** `output: "export"` forbids `rewrites()` in `next.config.ts`, but without a rewrite, `next dev`'s relative `/api/login` calls have nowhere to go. Fixed with Next's supported phase-based config (`next.config.ts` is now a function of `phase`): dev mode gets a rewrite proxying `/api/*` to `http://127.0.0.1:8000`, production/export mode gets `output: "export"`. `playwright.config.ts` now starts both `uvicorn` (port 8000) and `next dev` (port 3000) via an array of `webServer` entries.
- **Next.js 16's static export directory collision.** For a route like `/login`, Next writes both `login.html` (the real page) *and* a `login/` directory (RSC prefetch data, no `index.html` inside). Starlette's `StaticFiles` matches the directory first and then 404s. `NextStaticFiles` in `backend/app/main.py` now tries `<path>.html` *before* the raw path, with a regression test (`test_html_file_wins_over_a_same_named_directory`) covering it — caught by curling `/login` against the real built container, not by any local test alone, so container-level manual verification remains part of the checklist for a reason.

## Part 5: Database modeling

Propose a schema for the Kanban data, get sign-off before building on it.

- [x] Design SQLite schema: `users` (id, username, password — hardcoded row seeded on first run), `boards` (id, user_id, FK to users, one board per user per MVP constraint), `columns` (id, board_id, title, position), `cards` (id, column_id, title, details, position)
- [x] Write the schema as JSON (e.g. `docs/schema.json`) describing tables, columns, types, and relationships, mirroring the SQL design
- [x] Document the approach in `docs/DATABASE.md`: why this shape (maps directly onto the frontend's normalized `BoardData`/`Column`/`Card` types), how positions/ordering work, how it'll be created on first run
- [x] Present schema to user, get explicit sign-off — approved; login stays checking the hardcoded constants in `auth.py` (not the `users` table), and sessions stay in-memory (no `sessions` table)

**Tests / verification:** none (design-only phase) — verification is user approval of `docs/schema.json` and `docs/DATABASE.md`.

**Success criteria:** user has explicitly approved the schema before any backend code touches the database. Met.

## Part 6: Backend

Implement the API routes for reading/changing the Kanban board, backed by SQLite, created on first run if missing.

- [x] SQLite setup: on backend startup, create the db file and tables from the Part 5 schema if they don't exist; seed the hardcoded user and an initial board (reusing the frontend's `initialData` shape) if empty (`backend/app/db.py`: `init_db`, run from a FastAPI `lifespan` in `main.py`)
- [x] `GET /api/board` — returns the current user's board as `BoardData` JSON (columns + cards, matching `frontend/src/lib/kanban.ts` types)
- [x] `PATCH /api/columns/:id` — rename a column
- [x] `POST /api/cards` — create a card in a column
- [x] `PATCH /api/cards/:id` — edit a card's title/details, and/or move it (column + position)
- [x] `DELETE /api/cards/:id` — remove a card
- [x] All board routes require an authenticated session (401 otherwise) — `require_session` dependency from Part 4
- [x] Backend unit tests (pytest) for every route: happy path, not-found cases, unauthenticated case, and (for move/reorder) that column/card ordering persists correctly (`backend/tests/test_board.py`, 15 tests)

**Tests / verification:**

- `pytest` in `backend/` covers all routes above with real SQLite (temp db per test run via a `DATABASE_PATH` env var + `tmp_path`, not the dev db) — 27 tests total, verified
- Manual: created a card via `curl`, ran `docker restart pm-app-1` (not a fresh container — a real restart of the same one, volume intact), logged back in, confirmed the card was still there — verified
- Also added an in-process equivalent (`test_board_persists_across_reconnects_to_the_same_database`) that closes and reopens the SQLite connection against the same file, for a fast regression check without needing Docker

**Success criteria:** every board mutation available in the current frontend UI has a corresponding, tested backend route, and data survives a container restart. Met.

**Notable decisions:**

- **Board lookup ignores user identity.** Sessions (Part 4) are just a set of valid tokens with no user id attached, and there's only ever one board in this MVP, so `_get_board_id` in `board.py` does `SELECT id FROM boards LIMIT 1` rather than threading a user id through. Documented in the function's own comment so it isn't mistaken for an oversight if Part 5's "keep login on hardcoded constants" decision is revisited later.
- **Every mutating route returns the full updated `BoardData`**, not just the changed row — simplest contract for Part 7's frontend integration (replace local state with the response), and matches how the AI chat in Part 9/10 will need to push whole-board updates anyway.
- **Reordering renumbers positions sequentially** (0..n-1) on every move rather than using a gap/fractional scheme — simplest correct approach at this scale (a handful of cards per column), avoids ever needing to "rebalance" positions.

## Part 7: Frontend + Backend

Wire the frontend to the real backend so the app is a persistent Kanban board end to end.

- [x] Add a small fetch-based API client in `frontend/src/lib/` (`api.ts`) for board/card/column requests, using relative `/api/...` paths (same-origin, since FastAPI serves the static build)
- [x] Replace `KanbanBoard`'s hardcoded `initialData` with a fetch of `GET /api/board` on mount (loading state while fetching)
- [x] Wire `onRename`, `onAddCard`, `onDeleteCard`, and drag-end (move) handlers to call the corresponding backend routes instead of only updating local state; keep optimistic local updates for responsiveness, reconciling with the server response or rolling back on error
- [x] Handle the 401 case (session expired) by redirecting to `/login` (`UnauthorizedError` from `api.ts`, `onUnauthorized` prop threaded through `AuthGate` → `KanbanBoard`)

**Tests / verification:**

- Frontend unit tests updated to mock the API client instead of relying on `initialData` (`KanbanBoard.test.tsx`) — plus new `src/lib/api.test.ts` for the client itself; 25 frontend unit tests total, verified
- New Playwright e2e run against `next dev` + local backend (both started by `playwright.config.ts`'s `webServer` array from Part 4): log in, add a card, rename a column, drag a card between columns, reload the page, confirm changes persisted — verified, plus re-verified against the real Docker container via `curl`
- Backend pytest suite still green — 27 tests, verified

**Success criteria:** reloading the page (or restarting the container) never loses board changes made through the UI; the frontend has no more hardcoded board data. Met.

**Notable decisions:**

- **Every mutation reconciles by replacing the whole board with the server's response** (`.then(setBoard, handleApiError)`), and on error, `handleApiError` refetches the whole board from the server rather than manually rolling back to a locally-tracked "previous" snapshot per handler — simpler, and more correct (it converges on true server state instead of a possibly-stale local one).
- **Column rename is debounced (400ms)**, not sent on every keystroke — `onRename` fires on every `input` change (existing behavior from the local-state days), and calling the API per keystroke would be excessive. Local state still updates immediately for a responsive input; only the network call is debounced.
- **e2e tests no longer assume pristine seed data.** Once the board is really persisted, an assumption like "card-1 starts in col-backlog" only holds on the very first run — a later run (or a concurrent one) may have already moved it. `kanban.spec.ts` now creates its own uniquely-titled column rename / card per test instead. Also set `workers: 1` in `playwright.config.ts` since the board is shared, persistent state across all tests in a run — parallel workers would race each other mutating it. (`board.py`'s `add_card` originally had a real TOCTOU race on position assignment too, flagged here — since fixed with an explicit `BEGIN IMMEDIATE` transaction around the read-then-insert.)
- **The optimistic add-card update uses a temporary id** (`card-pending-<timestamp>`) swapped for the real server id on reconciliation — this briefly unmounts/remounts the card's DOM node (React key changes), which flaked the Playwright drag test until it was changed to wait for the `POST /api/cards` response before computing drag coordinates, rather than grabbing them right after the optimistic render.

## Part 8: AI connectivity

Add a minimal OpenRouter call from the backend, proven working before building the real chat feature.

- [x] `backend` OpenRouter client using `OPENROUTER_API_KEY` from `.env` (`backend/app/ai.py`: `complete()`), model `openai/gpt-oss-120b`
- [x] `POST /api/ai/test` (auth-gated like the other routes) sends a "what is 2+2?" prompt and returns the reply
- [x] Handle and surface API errors (missing key, network failure, non-2xx from OpenRouter) clearly — all raise `OpenRouterError`, mapped to a 502 at the route

**Tests / verification:** integration test (marked to skip if `OPENROUTER_API_KEY` is absent) that calls OpenRouter with the 2+2 prompt and checks the answer, plus unit tests (mocked `httpx.post`) for missing-key/network-error/non-200/malformed-response, plus route tests for the auth gate and 502 mapping — `backend/tests/test_ai.py`, 8 tests.

**Success criteria:** a real OpenRouter call succeeds against `openai/gpt-oss-120b` and the test asserts on the actual model output, not a mock. **Not yet met** — the `.env` key currently returns `401: {"error":{"message":"User not found.","code":401}}` from OpenRouter itself (not a bug here: the other 7 tests in `test_ai.py`, including auth gating and every error-handling path, pass). Everything else in this part is implemented and tested; re-run `uv run pytest tests/test_ai.py::test_complete_real_2_plus_2` once `.env` has a working key to close this out.

## Part 9: Structured AI board updates

Extend the AI call to always include the current board JSON plus the user's message and conversation history, and require Structured Outputs with a chat reply and an optional board update.

- [x] Define the Structured Output JSON schema: `{ reply: string, board_update: BoardData | null }` — full-board replacement, not a diff (see decisions below for why, and for how `board_update`'s wire shape differs slightly from the internal `BoardData`)
- [x] `POST /api/chat` — accepts `{message}` (see decisions: history is server-tracked per session, not client-supplied), loads the current board, calls OpenRouter with system prompt + board JSON + history + message, requests the structured schema, applies `board_update` to the database if present, returns `{reply, board: <updated BoardData or unchanged>}`
- [x] Validate `board_update` before applying (referenced column/card ids exist, no orphaned cards, no duplicate column ids, no card claimed by two columns) and reject/ignore invalid updates rather than corrupting the board (`backend/app/chat.py`: `parse_board_update` / `_validate_board_update`)
- [x] Conversation history persisted per session for the duration of the chat (in-memory `dict[session_id, list[message]]` in `chat.py`, cleared on logout — consistent with Part 5's decision to keep sessions themselves in-memory too)

**Tests / verification:**

- Backend tests (real OpenRouter call, skipped without an API key) for: a question that shouldn't change the board (reply only), and an instruction that should create/move/edit a card (board updates correctly and persists) — written, **blocked on the same `.env` key issue as Part 8** (`401: User not found`); everything else in this part is implemented and tested
- Backend unit tests (mocked OpenRouter response) for schema validation/rejection of a malformed `board_update` — plus route-level tests (reply-only, valid update applied+persisted, invalid update ignored, 401 without auth, 502 on `OpenRouterError`, history accumulates across calls) — `backend/tests/test_chat.py`, 15 tests, 13 passing / 2 blocked on the key
- Full backend suite: 49 tests, 46 passing (3 blocked on the key: 1 from Part 8's `test_ai.py`, 2 from `test_chat.py`) — verified
- Manual: rebuilt the Docker container, confirmed `/api/chat` returns 401 unauthenticated and a clean 502 (not a crash) with the current broken key

**Success criteria:** a chat message like "move the login bug card to Done" results in the correct database change and a sensible reply, verified against the real model at least once. **Not yet met** — blocked on a working `OPENROUTER_API_KEY`, same as Part 8. Re-run `uv run pytest tests/test_chat.py -k real` once `.env` has a working key.

**Notable decisions:**

- **`board_update` is a full-board replacement**, not a diff/patch — matches what was already flagged as the likely direction back in Part 6's notes. Applying it is a delete-and-reinsert (`board.py`'s new `replace_board`), simpler than diffing at this scale. The real risk with full-replacement is the AI silently *dropping* a card/column it wasn't asked to touch — mitigated only by an explicit system-prompt instruction ("include all the ones you didn't change"), not by any structural check (a valid-but-incomplete board is still schema-valid). Worth watching once this is tested against the real model.
- **`board_update`'s wire shape differs slightly from the internal `BoardData`**: `cards` is sent as an **array** of `{id, title, details}`, not the dict-keyed-by-id shape the frontend and internal API use. Strict-mode JSON Schema structured outputs don't support a dynamic dict of properties (`additionalProperties` with arbitrary keys isn't compatible with `strict: true`), so the array form is what's requested from the model; `parse_board_update` converts it to the dict-keyed `BoardData` immediately after parsing.
- **History is server-tracked per session, not client-supplied**, despite the plan's original `{message, history}` wording — the server already has to track sessions in memory (Part 4/5), so also holding conversation history there avoids the client re-sending a growing transcript on every request and avoids trusting client-supplied history. `POST /api/chat` only takes `{message}`.
- **`/api/ai/test` and `/api/chat` now duplicate less**: refactored `ai.py`'s `complete()` into a shared `_post_chat_completion` / `_extract_content` pair, with `complete()` (plain) and `complete_structured()` (JSON-schema mode) both thin wrappers over it — `chat.py` doesn't reimplement the OpenRouter HTTP/error-handling logic.

## Part 10: AI chat sidebar UI

Add the chat sidebar to the frontend, wired to `/api/chat`, refreshing the board automatically on AI-driven updates.

- [x] Sidebar component (collapsible, styled with the existing color tokens) with message list and input, alongside the Kanban board (`frontend/src/components/ChatSidebar.tsx`)
- [x] Sends user messages to `POST /api/chat` (history is server-tracked per session, per Part 9's decision — the sidebar just sends `{message}`), appends the AI reply to the message list
- [x] If the response includes an updated board, replace local board state with it so the Kanban UI reflects AI-made changes immediately (no manual refresh) — `onBoardUpdate` prop wired straight to `KanbanBoard`'s `setBoard`
- [x] Loading ("Thinking…") and error states for the chat call

**Tests / verification:**

- Frontend unit tests for the sidebar (mocked `@/lib/api`): starts collapsed, sending a message appends both messages, a response with a board update calls `onBoardUpdate`, a failed request shows an error and does not call `onBoardUpdate` — `ChatSidebar.test.tsx`, 3 tests; plus a `KanbanBoard.test.tsx` check that the toggle renders — 27 frontend unit tests total, all passing
- Playwright e2e (real backend): `tests/chat.spec.ts` creates a card, asks the assistant to move it to Done, confirms it moved without a reload — written and correctly exercises the whole path, but **currently fails for the same reason as Parts 8–9**: `/api/chat` returns 502 because of the `.env` key issue, so the card never moves. Re-run once the key works.
- Manual: visually checked the sidebar in a real browser (Playwright screenshot) and caught a real layout bug doing so — the fixed-position sidebar overlapped the rightmost board columns at normal viewport widths. Fixed by lifting the open/closed state into `KanbanBoard` (`ChatSidebar`'s new `onOpenChange` prop) so the board reserves right-padding (`xl:pr-[400px]`) while the sidebar is open. Re-verified with another screenshot.
- Full suites re-verified after the fix: 27/27 frontend unit tests, 7/8 e2e (1 blocked on the key), 46/49 backend (3 blocked on the key) — rebuilt and manually checked in the real Docker container too.

**Success criteria:** using the chat sidebar to ask the AI to create, edit, or move a card produces an immediate, correct, visible update to the Kanban board. **Not yet verified end-to-end** — blocked on the same `OPENROUTER_API_KEY` issue as Parts 8–9. Everything up to and including the OpenRouter call itself is implemented, tested, and (for the non-AI parts) working; re-run `npx playwright test chat.spec.ts` once `.env` has a working key to close this out — that's the single remaining gate on the whole app being fully functional.
