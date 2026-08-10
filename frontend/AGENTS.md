# Frontend

Next.js (App Router) frontend for the Kanban board, statically exported (`output: "export"` in `next.config.ts`) and served by the FastAPI backend — see [../backend/AGENTS.md](../backend/AGENTS.md) for how (`NextStaticFiles` resolves `/login` etc. to their pre-rendered `login.html`). `/` is gated behind a hardcoded login (Part 4). The board is backed by the real API and SQLite (Part 7) — no more hardcoded `initialData` in the running app; it survives reloads and container restarts. A collapsible AI chat sidebar (Part 10, `ChatSidebar.tsx`) lets the user ask the assistant to create/edit/move cards, applying `POST /api/chat`'s board response directly (see [../docs/PLAN.md](../docs/PLAN.md)) — this is the last piece of the MVP, and end-to-end verification of the AI path itself is currently blocked on a working `OPENROUTER_API_KEY` (see Part 8's note in the plan).

Because of static export, no Next.js server-side features (API routes, SSR, `next start`) are available — everything server-side goes through FastAPI. `npm run dev` still works normally for local development, but relative `/api/*` calls need something to answer them: `next.config.ts` is a phase-based function (`output: "export"` for builds, a dev-only rewrite proxying `/api/*` to `http://127.0.0.1:8000` for `next dev`) since `output: "export"` and `rewrites()` can't both be set. Run the backend locally (`uv run uvicorn app.main:app --reload` from `backend/`, or let `playwright.config.ts` start it) for `/login` to work under `npm run dev`.

## Stack

- Next.js 16 (App Router), React 19, TypeScript
- Tailwind CSS v4 (CSS-based config via `@theme inline` in `globals.css`, no `tailwind.config.js`)
- `@dnd-kit/core` + `@dnd-kit/sortable` for drag and drop
- Vitest + Testing Library for unit/component tests, Playwright for e2e

## Structure

```text
src/
  app/
    layout.tsx      RootLayout: Space Grotesk (display) + Manrope (body) fonts, metadata
    page.tsx         "/" route, renders <AuthGate /> (session check, then <KanbanBoard />)
    login/page.tsx    "/login" route: username/password form, calls lib/auth login()
    globals.css       Tailwind import + color tokens (--accent-yellow, --primary-blue, etc.)
  components/
    AuthGate.tsx             Client-side session check + redirect to /login; renders KanbanBoard with onLogout/onUnauthorized when authenticated
    KanbanBoard.tsx        Fetches BoardData from the API on mount (loading state), owns it in useState, DndContext, drag handlers, DragOverlay, renders ChatSidebar; mutations call lib/api with optimistic local updates
    ChatSidebar.tsx          Collapsible AI chat: message list + input, POSTs to lib/api's sendChatMessage, calls onBoardUpdate with the response's board; reports its open/closed state via onOpenChange so KanbanBoard can reserve layout space
    KanbanColumn.tsx        Droppable column: title edit, SortableContext over card ids, add-card form
    KanbanCard.tsx           Sortable card (useSortable): title, details, remove button
    KanbanCardPreview.tsx    Static card visual rendered inside DragOverlay while dragging
    NewCardForm.tsx           Inline toggle form to add a card to a column
  lib/
    kanban.ts        Types (Card, Column, BoardData), initialData (now only used as e2e/test fixture data, not by the app), pure logic (moveCard, createId)
    auth.ts            login()/logout()/getSession() fetch wrappers around /api/login, /api/logout, /api/session
    api.ts              fetchBoard/renameColumn/createCard/moveCard/deleteCard/sendChatMessage fetch wrappers around the backend routes; throws UnauthorizedError on a 401
tests/
  kanban.spec.ts      Playwright e2e: rename a column, add+drag a card, reload, confirm both persisted — logs in via helpers.ts in beforeEach since / is gated
  auth.spec.ts         Playwright e2e: logged-out redirect, login, wrong credentials, logout
  chat.spec.ts          Playwright e2e: add a card, ask the assistant to move it, confirm it moves without a reload — real backend call, currently blocked on the OpenRouter key (see docs/PLAN.md Part 10)
  helpers.ts            loginAsTestUser(page): logs in via page.request.post so UI tests don't repeat the login flow
```

Two routes exist: `/` (gated) and `/login`. The chat sidebar is not a route — it's a fixed-position overlay rendered on `/`.

## Data model (`src/lib/kanban.ts`)

```ts
export type Card = { id: string; title: string; details: string };
export type Column = { id: string; title: string; cardIds: string[] };
export type BoardData = { columns: Column[]; cards: Record<string, Card> };
```

Normalized shape: columns hold ordered `cardIds`; cards are keyed by id. This matches the MVP's "1 board per user" constraint — there is no `Board` wrapper type, and it mirrors the backend's `BoardData` pydantic model in `backend/app/board.py` exactly (routes return this shape directly). `initialData` (5 columns, 8 cards) is no longer used by the running app — it's kept only as fixture data for tests. `moveCard(columns, activeId, overId)` is a pure function handling same-column reorder, cross-column move, and drop-on-column-vs-drop-on-card — it only touches `columns`, not `cards`; `KanbanBoard` uses it to compute the optimistic local state during a drag, then derives the moved card's new column/position from the result to call `api.moveCard`.

## State management

Plain React `useState` in `KanbanBoard.tsx`, holding a `BoardData | null` (`null` while the initial `GET /api/board` is in flight). No Context/Redux/Zustand — a small fetch/mutation layer (`lib/api.ts`) plus local state was enough for a single-board app, no state management library needed.

Mutation pattern (`onRename`, `onAddCard`, `onDeleteCard`, drag-end): apply an optimistic local update to `board` immediately, fire the corresponding `lib/api` call, then `.then(setBoard, handleApiError)` — success replaces local state with the server's authoritative response (not just the changed piece), and `handleApiError` either calls `onUnauthorized` (401) or refetches the whole board to reconcile (any other error), rather than manually tracking a "previous" snapshot to roll back to per handler. Column rename is debounced 400ms (fires on every keystroke locally, but only the network call is throttled).

## Drag and drop

`dnd-kit`: `KanbanBoard` sets up `DndContext` (`PointerSensor`, 6px activation distance, `closestCorners` collision), tracks `activeCardId` for the `DragOverlay`. `KanbanColumn` uses `useDroppable` + `SortableContext` (`verticalListSortingStrategy`). `KanbanCard` uses `useSortable`. Reordering logic is delegated to `moveCard`.

## Styling

Tailwind v4, no config file — theme tokens are CSS custom properties in `globals.css`:

```css
--accent-yellow: #ecad0a;
--primary-blue: #209dd7;
--secondary-purple: #753991;
--navy-dark: #032147;
--gray-text: #888888;
```

plus derived `--surface`, `--surface-strong`, `--stroke`, `--shadow`. Consumed via arbitrary-value classes, e.g. `text-[var(--navy-dark)]`. This already matches the color scheme in the root [AGENTS.md](../AGENTS.md) — keep new UI (e.g. the future chat sidebar) consistent with these tokens rather than introducing new colors, as the login form (`src/app/login/page.tsx`) does.

## Tests

- `npm run test` / `test:unit` — Vitest: `src/lib/kanban.test.ts` (moveCard logic), `src/lib/auth.test.ts` and `src/lib/api.test.ts` (fetch wrappers, mocked `fetch`), `src/app/login/page.test.tsx` and `src/components/AuthGate.test.tsx` (mocked `fetch` + `next/navigation`), `src/components/KanbanBoard.test.tsx` (RTL, mocks `@/lib/api` entirely rather than `fetch` directly — renders columns, rename column, add/remove card, chat toggle present), `src/components/ChatSidebar.test.tsx` (mocks `@/lib/api`: starts collapsed, send a message, error case). 27 tests total.
  - When mocking `next/navigation`'s `useRouter` with `vi.mock`, return a **stable object reference** (module-level constant), not a new object literal per call — a fresh object each call changes a `useEffect([router])` dependency's identity on every render, causing the effect (and any `fetch` it makes) to re-run repeatedly. Bit us in `AuthGate.test.tsx`.
  - When a test mocks multiple endpoints on the same `fetch`, use `mockImplementation` (branch on the URL), not `mockResolvedValue` with one shared `Response` — a `Response` body can only be read once, so a single mocked instance breaks the second real endpoint it's reused for. Also bit us in `AuthGate.test.tsx` once `KanbanBoard` started calling `/api/board` itself alongside `AuthGate`'s own `/api/session` check.
- `npm run test:e2e` — Playwright. `playwright.config.ts` starts **two** `webServer`s: the backend (`uv run --directory ../backend uvicorn ...` on port 8000, `DATABASE_PATH=data/e2e.db` so it doesn't touch your manual-testing dev db) and `next dev` (port 3000, baseURL). `workers: 1` — the board is now real, shared, persistent state across the whole run, so parallel workers would race each other mutating it. `tests/kanban.spec.ts`, `tests/auth.spec.ts`, and `tests/chat.spec.ts` all need the backend since `/` is gated.
  - Because the board persists across separate `npx playwright test` invocations (not just within one run), tests don't assume pristine seed data (no "card-1 starts in col-backlog") — each creates its own uniquely-titled column rename / card per test instead.
  - When asserting on a card right after an optimistic-then-reconciled mutation (e.g. add-card), wait for the mutation's network response before computing anything DOM-position-dependent (`page.waitForResponse`) — the optimistic card has a temp id, gets swapped for a differently-`key`'d DOM node once the real one lands, and grabbing a bounding box mid-swap flakes.
  - `chat.spec.ts` is currently failing, not flaky — blocked on the same `OPENROUTER_API_KEY` issue as the backend's real-call tests (see `docs/PLAN.md` Part 8). Everything else (7/8 e2e tests) is green.
  - Verify new UI in an actual browser, not just tests: a Playwright screenshot of the chat sidebar caught a real layout bug (fixed-position sidebar overlapping the rightmost board columns) that no unit or e2e assertion would have noticed, since nothing was checking element positions.

## Integration points for later phases

None currently planned beyond Part 10 — this is the last part of `docs/PLAN.md`. The one open item across the whole app is the `OPENROUTER_API_KEY` in `.env` needing to be replaced with a working one (Parts 8, 9, and 10's AI-dependent tests are all blocked on it); everything else is implemented, tested, and verified.
