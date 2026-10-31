# Smart Skin Care Assistant — Frontend

## Current status: Frontend Phase 5 complete (chat)

This is the foundation phase only — proving the frontend and backend
actually communicate, with real routing for every page in the
architecture, before any page gets real content.

**Built and verified:**
- React + TypeScript + Vite, Tailwind CSS v4 (via `@tailwindcss/vite`)
- React Router with a real route for all 9 planned pages
- A typed Axios API client (`src/services/api.ts`), base URL from
  `VITE_API_BASE_URL` — never hardcoded
- `<ConnectionStatus>` — calls the real backend's `GET /api/v1/health`
  and shows what actually comes back. **Verified both ways**: with the
  backend running it shows "Backend connected" with the real service
  name; with the backend stopped it shows "Backend unreachable —
  Network Error" with a red dot. This is not a hardcoded "always
  green" indicator.
- `npx tsc --noEmit` — zero type errors (both phases)
- `npm run build` — builds cleanly
- **Full real end-to-end auth flow, driven through the actual UI by a
  real browser** (not just unit tests): visiting a protected route
  while logged out redirects to `/login`; a brand-new signup through
  the real form logs in and lands on the dashboard with the real name
  shown; reloading the page keeps the session (token verified against
  `/auth/me`); logging out and revisiting a protected route redirects
  again; wrong password, duplicate email, and a weak password on
  signup each show the real backend's own error text.
- **Full real end-to-end dashboard/profile flow**: a brand-new user's
  dashboard honestly shows "No profile set yet" / "0 journal entries" /
  "No routines logged yet" — not fabricated placeholder numbers; setting
  a profile (skin type + 2 concerns + notes) through the real form,
  reloading the page, and confirming via the actual button state and
  textarea value that the data came back from the backend, not just
  local state; confirming the dashboard then reflects the saved profile.
- **A real bug was found and fixed during this testing** — not in the
  app, but in the *test script*: Playwright's plain `text=` selector was
  unreliable against buttons using a `transition-colors` CSS class,
  intermittently failing with "element detached from DOM." Switching to
  role-based exact-match locators (`get_by_role('button', name=...,
  exact=True)`) fixed it and was verified to work reliably. Documented
  here because it looked exactly like an app bug at first and needed a
  real investigation to rule out, not a shrug.
- **React StrictMode note**: in dev mode you'll see each page's initial
  data fetch run twice (and its console 404 logged twice, for a
  brand-new user with no profile yet) — this is React 18's intentional
  double-invocation of effects in development only, to help surface
  cleanup bugs. It does not happen in a production build and is not an
  application bug.
- **Full real end-to-end journal flow**: create an entry through the
  UI, confirm it's visible; attempt a second entry for the same date,
  confirm the real backend 409 message is shown; edit the entry,
  confirm the new text is visible; reload the page, confirm the edit
  survived (came from the backend, not local state); delete it,
  confirm the empty state returns.
- **Full real end-to-end products flow**: confirm the empty-catalog
  message is honest (no fake products) before seeding; run the real
  `seed_demo_products` script; search for a real seeded product by
  name; open its detail view and confirm a real ingredient, its real
  precaution text, and the sample-data source disclosure all render
  correctly.
- **Full real end-to-end chat flow**: a normal curated-topic question
  gets the real knowledge-base answer with its real source citation
  and the real medical disclaimer, correctly labeled as mock; a message
  describing an emergency gets the real, distinct safety response
  instead (confirmed it's a *different* message, not the same generic
  answer); starting a second conversation and reloading the page shows
  both conversations in the sidebar with real auto-generated titles;
  the Send button is disabled on an empty message.

**Phase 2 — authentication, added on top of Phase 1:**
- Real Login/Signup form (`src/pages/Login.tsx`) — one page, tabbed
  between the two modes, posting to the real `/api/v1/auth/register`
  and `/api/v1/auth/login` endpoints.
- `AuthProvider` / `useAuth()` (`src/hooks/useAuth.tsx`) — the single
  source of truth for the current user and session. On every page
  load, a stored token is verified against the real `GET /auth/me`
  (not trusted blindly); an expired/invalid token is cleared
  automatically.
- `ProtectedRoute` — Dashboard, Chat, Acne Analysis, Skin Assessment,
  Products, Journal, and Reports all redirect to `/login` if there's
  no authenticated user (matches the backend, which requires auth on
  every one of these).
- Logout always clears local session state, even if the server call
  itself fails — never leaves the UI stuck thinking it's logged in.
- Error messages shown to the user are the **real backend messages**,
  not generic ones — including correctly handling FastAPI's two
  different error shapes (a plain string for 401/409, an array of
  Pydantic errors for 422), verified against the live backend's actual
  responses before writing the parsing code.
- **Google login is visibly not connected** — the login page says so
  directly, rather than showing a dead/fake button.

**Phase 3 — dashboard & skin profile, added on top of Phase 2:**
- `src/pages/SkinAssessment.tsx` — real form against the backend's
  exact schema: skin type (one of 5 fixed values) and concerns (one of
  7 fixed tags — both verified against `app/schemas/profile_schema.py`
  and `app/database/models.py` directly, not guessed), plus free-text
  sensitivity notes. Loads the existing profile on mount (handling "no
  profile yet" as a normal state, not an error, since the backend
  returns 404 for that case) and saves via the real `PUT /api/v1/profile`.
- `src/pages/Dashboard.tsx` — welcome message with the real logged-in
  name, the real skin profile summary, a real 30-day activity summary
  pulled from `GET /api/v1/reports/summary` (journal entry count,
  routine completion), the report's own disclaimer text shown
  verbatim, and quick links to the other sections.
- `src/services/profile.ts`, `src/services/reports.ts` — typed exactly
  to the backend's real response shapes.
- **Full real end-to-end flow verified** (see below) — not just that
  it compiles.

**Phase 4 — journal & products, added on top of Phase 3:**
- `src/pages/Journal.tsx` — full CRUD against the real backend: create
  an entry (date + feeling tags from the fixed 8-tag vocabulary +
  notes), list, inline edit, delete. The backend's one-entry-per-day
  rule is enforced server-side and the real `409` message is shown
  verbatim when you try to add a second entry for a date you already
  logged.
- `src/pages/ProductGuide.tsx` — search the real product catalog,
  open a detail view showing real ingredients with their precautions,
  and `is_sample_data` + `source` always shown so demo content is
  never mistaken for a verified listing. When the catalog is empty, it
  says so honestly and points at the real seed script
  (`python -m scripts.seed_demo_products`) rather than showing fake
  products.
- `src/services/journal.ts`, `src/services/products.ts` — typed
  exactly to the backend's real schemas.

**Phase 5 — chat, added on top of Phase 4:**
- `src/pages/Chatbot.tsx` — a real conversation UI: a session sidebar
  (switch between conversations, start a new one, delete one), a
  message thread, and a send box wired to the real
  `POST /api/v1/chat`, `GET /chat/sessions`, `GET /chat/sessions/{id}`,
  and `DELETE /chat/sessions/{id}` endpoints.
- **Every assistant message honestly shows "Mock / rule-based response
  — no real AI model is connected yet"** when `is_mock_response` is
  true — which today is always, since only the mock provider exists.
  This is not a cosmetic label added for show: it's read directly off
  the real backend flag, verified by inspecting the real response.
- **The safety layer is shown exactly as the backend returns it** — a
  message describing an emergency (e.g. swelling + high fever) gets
  the real, fixed safety response, not a model-generated one, and it's
  *also* correctly labeled as a mock/rule-based response (because the
  backend marks it that way too — the LLM was never called for it,
  which the backend's own test suite already proves separately).
- Optimistic UI: your message appears immediately on send; if the
  request fails, it's rolled back and your text is restored in the
  input box — because the backend's `process_user_turn` doesn't
  persist anything on a failed turn either, so the UI must match that
  truth, not pretend the message was sent.
- `src/services/chat.ts` — typed exactly to the backend's real schema.
- Not built yet: Acne Analysis, and the full Reports page (with
  charts — the Dashboard already shows a summary). Each still an
  honest placeholder naming its own upcoming phase.

## Setup

```bash
cd frontend
npm install
cp .env.example .env
# edit .env if your backend isn't at http://127.0.0.1:8000
npm run dev
```

The backend must be running separately (see `../backend/README.md`)
for `<ConnectionStatus>` to show "connected" — that's by design, not a
bug, so you always know the real state.

```bash
# in another terminal
cd ../backend
# (venv activated, .env configured, migrations applied - see its README)
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:5173/ — note **5173**, Vite's default port,
which is also what the backend's `CORS_ORIGINS` is already configured
to allow (see `backend/.env.example`). If you run the frontend on a
different port, update the backend's CORS config to match, or requests
will be blocked by the browser.

## Scripts

```bash
npm run dev         # dev server with hot reload
npm run build        # type-check (tsc -b) + production build
npx tsc --noEmit     # type-check only, no build
```

## Project layout

```
frontend/
  src/
    main.tsx            React root, wraps App in BrowserRouter
    App.tsx              route definitions for all 9 pages
    components/
      Layout.tsx          top nav + responsive shell + auth-aware header
      ConnectionStatus.tsx  live backend health check (see above)
      ProtectedRoute.tsx    redirects to /login if not authenticated
      PagePlaceholder.tsx   shown by pages not yet built
    hooks/
      useAuth.tsx           AuthProvider + useAuth() — session state
    pages/
      Home.tsx             real landing-page content
      Login.tsx             real login/signup (Phase 2)
      Dashboard.tsx         real dashboard: profile + activity summary (Phase 3)
      SkinAssessment.tsx    real skin-profile form (Phase 3)
      Journal.tsx            real journal CRUD (Phase 4)
      ProductGuide.tsx       real product search + detail (Phase 4)
      Chatbot.tsx             real chat UI + sessions (Phase 5)
      AcneAnalysis.tsx, Reports.tsx
        - placeholders today; each names its planned phase
    services/
      api.ts               the one Axios instance + typed health call
      auth.ts              auth API calls + real-error-shape parsing
      profile.ts            profile API calls, typed to the real backend schema
      reports.ts            report-summary API call
  .env.example
```

## Why Tailwind v4 has no tailwind.config.js

Tailwind v4 is configured via the `@tailwindcss/vite` plugin (see
`vite.config.ts`) and a single `@import "tailwindcss";` in
`src/index.css` — there's no separate config file to maintain in this
version, by design.
