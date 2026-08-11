# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Project Management MVP: single-user (hardcoded `user`/`password`) Kanban board with an AI chat sidebar that can create/edit/move cards. NextJS frontend statically exported and served by a FastAPI backend, everything packaged into one Docker container. See [AGENTS.md](AGENTS.md) for the business requirements and [docs/PLAN.md](docs/PLAN.md) for what's implemented per part.

Detailed, up-to-date conventions live in per-directory `AGENTS.md` files — read them before working in that area:
- [backend/AGENTS.md](backend/AGENTS.md) — FastAPI structure, auth, db, AI/chat internals
- [frontend/AGENTS.md](frontend/AGENTS.md) — Next.js structure, data model, state/drag-and-drop, test gotchas
- [docs/DATABASE.md](docs/DATABASE.md) — SQLite schema and seeding

## Commands

Backend (from `backend/`, uses `uv`):
```
uv sync                              # install deps
uv run uvicorn app.main:app --reload # run dev server (port 8000)
uv run pytest                        # run all tests
uv run pytest tests/test_board.py -k test_name  # run a single test
```

Frontend (from `frontend/`):
```
npm run dev          # dev server, port 3000 (proxies /api/* to backend on 8000)
npm run build         # static export (output: "export")
npm run lint
npm run test:unit     # Vitest (or: npm run test)
npm run test:unit:watch
npm run test:e2e      # Playwright e2e; starts backend + next dev itself
npm run test:all       # unit + e2e
```
Single Vitest file: `npx vitest run src/lib/kanban.test.ts`. Single Playwright spec: `npx playwright test tests/auth.spec.ts`.

Full stack via Docker (from repo root):
```
scripts/start.sh   # or start.ps1 on Windows — docker compose up -d --build, app at :8000
scripts/stop.sh    # or stop.ps1
```

CI (`.github/workflows/`) runs backend pytest, frontend lint + unit tests, and a non-blocking e2e job on every push/PR to `main`.

## Architecture

- FastAPI serves both the API (`/api/*`) and the pre-built Next.js static export (everything else), via a custom `NextStaticFiles` class in `backend/app/main.py` that resolves routes like `/login` to their exported `login.html`.
- Frontend is a static export (no Next server-side features); local dev (`next dev`) proxies `/api/*` to a locally-running backend since there's no server to answer those routes itself.
- Data model is normalized and shared in shape across three layers: SQLite (`columns`/`cards` tables) → backend pydantic models (`backend/app/board.py`) → frontend TS types (`frontend/src/lib/kanban.ts`) — columns hold ordered `cardIds`, cards are keyed by id.
- Auth is a single hardcoded credential pair; sessions and (per Part 9) AI chat history are both in-memory dicts/sets on the backend process, not persisted — acceptable for this MVP, cleared on restart/logout.
- AI chat (`backend/app/chat.py`, `backend/app/ai.py`) calls OpenRouter (`openai/gpt-oss-120b`) requesting structured JSON output (`{reply, board_update}`); a returned `board_update` is a full-board replacement, validated for internal consistency, then persisted via `replace_board` — not a diff/patch.
- `backend/app/mcp_server.py` (untracked/in progress) exposes the board as MCP tools over stdio, talking to `app.board`/`app.db` directly rather than through the HTTP API.

## Coding standards (from AGENTS.md)

- Use latest versions of libraries and idiomatic approaches.
- Keep it simple — no over-engineering, no unnecessary defensive programming, no speculative features.
- Be concise; no emojis, ever.
- When hitting issues, find root cause with evidence before fixing — don't guess.
