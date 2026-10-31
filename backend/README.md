# Smart Skin Care Assistant — Backend

Educational skin-care assistant API. **This is informational and
tracking software, not a diagnostic or prescribing system.** Any acne
image analysis added in a later phase will be labeled
experimental/research-only.

## Current status: Phase 7 complete (products & reports)

**Phase 1 — backend foundation:**
- FastAPI app with `GET /` and `GET /api/v1/health`
- Centralized configuration (`app/core/config.py`) using
  `pydantic-settings`, reading from environment variables / `.env`
- CORS configured from the environment, with a hard safety check: the
  app refuses to start if you set a wildcard origin (`*`) together with
  `CORS_ALLOW_CREDENTIALS=true`
- Centralized error handling — unexpected errors return a generic JSON
  message to the client and the real detail to the server log, never a
  raw stack trace to the caller

**Phase 2 — database:**
- SQLAlchemy engine + session factory (`app/database/connection.py`),
  SQLite by default, one-line switch to PostgreSQL later via
  `DATABASE_URL`
- `get_db()` FastAPI dependency, ready for routes in later phases
- All 12 planned tables defined (`app/database/models.py`): users,
  skin_profiles, chat_sessions, chat_messages, journal_entries,
  routines, routine_items, routine_logs, products, ingredients,
  product_ingredients, ai_analysis_history
- Alembic migrations wired to the app's own settings and models (one
  database URL, configured once) — initial migration generated,
  applied, and rolled back successfully as a real test, not just
  written
- Privacy rules enforced at the schema level, not just as comments:
  `journal_entries.photo_path` exists but nothing writes to it yet;
  `ai_analysis_history` has no image column at all, and a test asserts
  it never silently grows one

**Phase 3 — authentication:**
- `POST /api/v1/auth/register`, `/login`, `GET /me`, `POST /logout` —
  see examples below
- Passwords hashed with Argon2id (via `pwdlib`) — plaintext is never
  stored, and `UserOut` (the only shape a user is ever returned as)
  has no password field at all, so no route can accidentally leak one
- JWT access tokens (30 min by default), with a `jti` on every token so
  logout can revoke that *specific* token without affecting a user's
  other active sessions (e.g. on another device)
- `get_current_user` — the one reusable dependency every protected
  route uses; identity always comes from the verified token, never
  from anything the client sends
- `ensure_owner` — the one place "does this record belong to this
  user" is checked; written now so Phase 4's profile/journal/routine
  endpoints call it instead of each reinventing the check
- Login and registration schema additions migrated in properly
  (`users.full_name`, `revoked_tokens` table) — applied and rolled
  back as a real test, not just generated

**Phase 4 — profile & journal:**
- `GET /api/v1/profile`, `PUT /api/v1/profile` — the current user's
  skin profile (preferences, explicitly not a diagnosis). PUT creates
  it if absent, partial-updates it if present (omitted fields are left
  unchanged, not wiped).
- `GET/POST /api/v1/journal`, `GET/PUT/DELETE /api/v1/journal/{id}` —
  full journal CRUD, one entry per day per user.
- This is the first phase where `ensure_owner` does real work: journal
  entries are addressed by id, so each single-entry route loads the row
  and checks ownership before acting. A row that belongs to someone
  else returns **404, identical to a row that doesn't exist** — no
  information leaks about other users' data.
- Input is validated with small closed vocabularies (skin concerns,
  feeling tags) so free-text medical/diagnostic terms can't be stored;
  notes have length limits; journal dates can't be in the future.
- **Photos are still not accepted anywhere.** `photo_path` exists on
  the model but is not part of any Phase 4 request or response schema —
  image upload (with the private storage / consent / deletion controls
  the brief requires) is its own later piece of work.

**Phase 5 — chatbot:**
- `POST /api/v1/chat`, `GET /chat/sessions`, `GET /chat/sessions/{id}`,
  `DELETE /chat/sessions/{id}` — authenticated, per-user conversations.
- **Provider-agnostic design:** the app talks to an `LLMProvider`
  interface, not a vendor. The only implementation today is
  `MockProvider`, which answers from a curated, source-attributed
  knowledge base with no network call and no API key. A real provider
  is added later as another class — endpoints don't change. Every
  mock/safety answer is marked `is_mock: true` so the frontend can
  label it honestly.
- **No schema changes** — the `chat_sessions` / `chat_messages` tables
  from Phase 2 already fit, including the `is_mock_response` flag. No
  migration was needed.
- **Medical-safety layer** (`app/services/safety_service.py`): a
  user's message is screened *before* it reaches the provider. Messages
  suggesting an emergency (e.g. trouble breathing, facial swelling,
  high fever, spreading redness, severe pain) get a fixed "seek care
  now" response and **the LLM is never called** for them. Messages
  suggesting self-harm get a separate response pointing to human crisis
  support. Normal answers always carry a medical disclaimer, and the
  provider is given a system instruction constraining it to educational
  information only.
- **Failure handling:** provider timeouts/errors (and any unexpected
  provider exception) become a clean `503`, and a failed turn persists
  **nothing** — no dangling user message without a reply, so it can be
  retried.

> **Safety is not claimed on the basis of passing tests.** The safety
> layer is a conservative keyword-and-rule guardrail around an
> *educational* tool. It cannot reliably detect every emergency, and
> the tests only prove the rules fire as written — not that the
> assistant is medically safe. This app does not diagnose, prescribe,
> or replace a doctor.

**Phase 6 — acne analysis (`POST /api/v1/acne/analyze`):**
- **No trained model exists in this repository.** The whole project
  tree and the uploads were searched for a checkpoint
  (`.pt`/`.pth`/`.ckpt`/`.onnx`/`.safetensors`/`.h5`/`.pkl`), a model
  config, a class map, and any training/eval/inference code — **none
  were found.** A dataset is not a trained model.
- Per the brief, the endpoint therefore returns an explicit
  `model_status: "model_not_configured"` with `predicted_class: null`
  and `raw_score: null` — it makes **no prediction and fabricates no
  confidence score.** `is_diagnosis` is always `false`.
- **The image-handling and privacy layers are fully built and tested
  regardless.** Uploads are validated by actually decoding the bytes
  (not trusting the filename or content-type), limited by size, and
  restricted to JPEG/PNG/WEBP. Images are held in memory only, used for
  the one request, and **never written to disk or persisted.** The
  response never contains a filesystem path or stored-image id.
- **No fabrication even if mis-configured:** if someone sets
  `ACNE_MODEL_PATH` to a real file before inference is actually wired
  to that specific model, the endpoint returns `503`, not a guessed
  answer — tested.
- PyTorch is deliberately **not** installed yet (no model to run). It
  will be added only when a verified checkpoint exists.

**Phase 7 — products, routines & reports:**
- `GET /api/v1/products`, `GET /products/{id}` — read-only catalog
  search. Every product reports `is_sample_data` and `source`, so demo
  content can never be mistaken for a verified listing (no invented
  prices, availability, or medical effectiveness).
- **Scope note — routines:** the `routines`/`routine_items`/
  `routine_logs` tables existed since Phase 2 but had **no endpoints
  at all**, so there was no way to ever create a routine or log a day
  as completed. Minimal CRUD was added as a necessary prerequisite for
  routine-completion reporting to mean anything: `POST/GET /routines`,
  `GET/DELETE /routines/{id}`, `POST /routines/{id}/log` (upserts by
  date, so correcting a log entry doesn't require deleting it first).
- `GET /api/v1/reports/summary?days=30` — the caller's own journal
  entry count, feeling-tag frequency, and routine completion rate over
  the period. **Always carries a disclaimer** that this reflects
  logged activity only, not a measure of clinical improvement — per
  the project brief, journal tags are never interpreted as proof skin
  is getting better or worse.
- `scripts/seed_demo_products.py` — optional, not run automatically;
  inserts a few clearly-marked sample products so there's something to
  browse locally. Safe to re-run (skips existing rows).
- **No schema changes.** All tables already existed from Phase 2.

**Not implemented yet**: the acne model *itself* — see "Acne analysis"
below (and the separate `ml/acne_model/` training package) for what's
needed to enable real predictions.

Automated tests: **94 passing** (4 Phase 1, 12 Phase 2, 19 Phase 3,
18 Phase 4, 16 Phase 5, 9 Phase 6, 16 new for Phase 7).

## Products, routines & reports — how to use them

```bash
# Browse the catalog (optionally seed demo data first — see below)
curl "http://127.0.0.1:8000/api/v1/products?q=cleanser" -H "Authorization: Bearer <token>"
curl http://127.0.0.1:8000/api/v1/products/1 -H "Authorization: Bearer <token>"

# Create a routine, then log today as completed
curl -X POST http://127.0.0.1:8000/api/v1/routines \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"routine_type": "morning", "items": [{"product_id": 1, "step_order": 1}]}'
curl -X POST http://127.0.0.1:8000/api/v1/routines/1/log \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"log_date": "2026-10-28", "completed": true}'

# Your activity summary (default last 30 days)
curl "http://127.0.0.1:8000/api/v1/reports/summary?days=30" -H "Authorization: Bearer <token>"
```

### Seeding demo product data (optional)

```bash
python -m scripts.seed_demo_products
```
Inserts a handful of sample cleansers/moisturizers/exfoliants with
ingredients, all marked `is_sample_data: true`. Safe to run more than
once.

## Acne analysis — current contract and what's needed to enable it

### API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/acne/analyze \
  -H "Authorization: Bearer <token>" \
  -F "image=@/path/to/face.jpg"
```
Response today (no model configured):
```json
{
  "model_status": "model_not_configured",
  "predicted_class": null,
  "raw_score": null,
  "is_diagnosis": false,
  "note": "No trained acne model is configured, so no prediction was made. ..."
}
```
- Requires authentication (`401` without a token).
- Accepts JPEG / PNG / WEBP only, decoded to confirm they're real
  images. Non-images and corrupt images → `422`. Unsupported formats
  (even with a lying content-type) → `422`. Over `ACNE_MAX_IMAGE_MB`
  (8 MB default) → `413`.

### What's required to enable real inference (none of this is guessed)

When a verified checkpoint becomes available, the following must be
confirmed **before** writing inference, and `_load_model()` /
`_run_inference()` in `app/services/acne_service.py` filled in to match
it exactly:
1. The real **architecture** (e.g. ResNet-18 or otherwise) and how the
   checkpoint was saved (full model vs `state_dict`).
2. The exact **input size** and **preprocessing** used at training time
   (resize, normalization mean/std, channel order) — inference
   preprocessing must match training preprocessing.
3. The real **class mapping** (how many classes, and what each index
   means). "It's a ResNet-18" does not tell us the classes.
4. The **evaluation results** on an appropriate held-out set — until
   then, no accuracy or reliability may be claimed.

Load the checkpoint with `weights_only=True` where supported, and
verify `torch.cuda.is_available()` and the installed build before
assuming GPU inference (the driver reporting a CUDA version does not
mean the installed PyTorch build uses the GPU — see hardware notes).

### Configuration

```
ACNE_MODEL_PATH=        # empty until a VERIFIED checkpoint exists; a dataset is not a model
ACNE_MAX_IMAGE_MB=8
```

> **No accuracy or clinical reliability is claimed.** There is no model
> yet, and even once one is added it will be labeled
> experimental/research-only and is not a medical diagnosis. Claims of
> accuracy require evaluation on an appropriate held-out dataset across
> varied skin tones, lighting, and image quality — which has not been
> done.

## Chatbot — how to use it

All chat endpoints require the `Authorization: Bearer <token>` header.

```bash
# Start a new conversation (omit session_id)
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"message": "I have mild acne, what helps?"}'
# -> { "session_id": 1, "reply": {...}, "is_mock": true }

# Continue the same conversation
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"session_id": 1, "message": "and what about sunscreen?"}'

# List your conversations
curl http://127.0.0.1:8000/api/v1/chat/sessions -H "Authorization: Bearer <token>"

# Read one conversation with all its messages
curl http://127.0.0.1:8000/api/v1/chat/sessions/1 -H "Authorization: Bearer <token>"

# Delete a conversation (and its messages)
curl -X DELETE http://127.0.0.1:8000/api/v1/chat/sessions/1 -H "Authorization: Bearer <token>"
```

`message` must be non-empty and at most `CHAT_MESSAGE_MAX_CHARS` (2000
by default). A conversation you don't own returns `404` on read,
delete, or an attempt to post into it — identical to a non-existent
one. Your session list only ever contains your own conversations.

### Chatbot configuration

```
LLM_PROVIDER=mock          # only "mock" is implemented today
LLM_API_KEY=               # unused by the mock; read server-side only when a real provider exists
LLM_TIMEOUT_SECONDS=20
CHAT_HISTORY_LIMIT=20      # how many prior messages are sent as context
CHAT_MESSAGE_MAX_CHARS=2000
```
The backend runs and every test passes with **no LLM credentials at
all** — the mock provider is fully offline. When a real provider is
added, its key is read from the environment and never exposed to the
frontend (the frontend only ever calls this backend, never the AI
vendor directly).

### Chatbot architecture (how a message flows)

```
POST /chat
  -> resolve/create the user's own ChatSession (ownership checked)
  -> safety_service.screen_user_message()
       -> emergency/crisis?  persist a fixed safe reply, DO NOT call the LLM
  -> llm_service provider.generate()      (mock today; real later)
       -> provider error?  nothing saved, return 503
  -> safety_service.append_disclaimer()
  -> persist user message + assistant message together
```

## Profile & journal — how to use them

All of these require the `Authorization: Bearer <token>` header from
login. Without it, every one returns `401`.

### Skin profile

```bash
# Set (or partially update) your profile
curl -X PUT http://127.0.0.1:8000/api/v1/profile \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"skin_type": "oily", "concerns": ["acne", "redness"]}'

# Read your profile
curl http://127.0.0.1:8000/api/v1/profile -H "Authorization: Bearer <token>"
```
`skin_type` is one of: `dry`, `oily`, `combination`, `balanced`,
`unsure`. `concerns` must come from a fixed list (`acne`, `dryness`,
`redness`, `texture`, `oiliness`, `sensitivity`, `dullness`) — anything
else is rejected with `422`, so the profile stays preference data, not
free-text medical claims.

### Journal

```bash
# Create today's entry
curl -X POST http://127.0.0.1:8000/api/v1/journal \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"entry_date": "2026-10-27", "notes": "Skin felt calm", "skin_feeling_tags": ["calm"]}'

# List your entries (newest first; supports ?limit= and ?offset=)
curl http://127.0.0.1:8000/api/v1/journal -H "Authorization: Bearer <token>"

# Read / update / delete one entry (must be yours)
curl http://127.0.0.1:8000/api/v1/journal/1 -H "Authorization: Bearer <token>"
curl -X PUT http://127.0.0.1:8000/api/v1/journal/1 \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"notes": "updated"}'
curl -X DELETE http://127.0.0.1:8000/api/v1/journal/1 -H "Authorization: Bearer <token>"
```
One entry per day: a second POST for the same date returns `409`. The
entry date can't be in the future. `skin_feeling_tags` come from a
fixed list (`calm`, `irritated`, `dry`, `oily`, `breakout`,
`improving`, `itchy`, `normal`).

**Ownership:** requesting, updating, or deleting an entry that belongs
to another user returns `404` — the same as a non-existent entry, on
purpose. Your journal list only ever contains your own entries.

## Authentication — how to use it

### Register

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Asha Rao", "email": "asha@example.com", "password": "StrongPass1"}'
```
Password rule, enforced on the server: **at least 8 characters, at
least one letter, at least one digit.** Returns `201` and the created
user (no password field). `409` if the email is already registered.

### Log in

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "asha@example.com", "password": "StrongPass1"}'
```
Returns `access_token`, `expires_at`, and the user's own profile. A
wrong password and a non-existent email both return the exact same
`401 Incorrect email or password.` — this is intentional, so a caller
can never use the login endpoint to check which emails are registered.

### Call a protected endpoint

```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <paste the access_token here>"
```
`401` with no header, an invalid token, an expired token, or a token
signed with the wrong secret.

### Log out

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>"
```
**What logout actually does:** a JWT is normally stateless — the
server doesn't track it until something is done to revoke it. Logout
adds that one token's `jti` to a small `revoked_tokens` table; every
protected request checks that table. After logout, *that exact token*
is rejected immediately, even though it hasn't reached its 30-minute
expiry yet. Logging in again issues a brand-new token. Logging out
does **not** affect any other active token the same user might have
(e.g. a second device that's still logged in) — that's by design, not
a gap.

**Known limitation:** revoked tokens are never deleted from the table
once they'd have expired anyway. For a real deployment this wants a
periodic cleanup job; it doesn't exist yet. For local development and
a small number of users this is not a practical problem.

### Try it from /docs

1. Start the server, open `http://127.0.0.1:8000/docs`.
2. Expand `POST /api/v1/auth/register`, click "Try it out," fill in the
   three fields, execute.
3. Expand `POST /api/v1/auth/login`, same email/password, execute, copy
   the `access_token` value from the response (just the token itself,
   no `Bearer ` prefix).
4. Click the padlock icon (top right of the page, or on any protected
   endpoint), paste the token into the "Value" field, click Authorize.
5. Now `GET /api/v1/auth/me` and `POST /api/v1/auth/logout` will work
   from the "Try it out" button without manually adding a header.

### Configuring secrets

Set a real `SECRET_KEY` in `.env` — generate one with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
If you don't set one, the app will still start locally (with a warning)
using a random key generated for that process only — every restart
invalidates every token issued before it. **In production the app
refuses to start** if `SECRET_KEY` is missing, the development
placeholder, or shorter than 32 characters (`APP_ENV=production`
triggers this check).

## Google OAuth — not implemented yet, here's exactly what it needs

The project brief is explicit: don't fake Google authentication, and
document the real setup instead of guessing. The schema is already
compatible (`users.google_sub`, nullable, unique; `hashed_password` is
nullable so a Google-only account needs no password) — no migration
will be needed when this is built.

**Google Cloud Console setup (one-time, by whoever owns the project):**
1. Create a project (or use an existing one) at
   https://console.cloud.google.com/
2. Configure the OAuth consent screen (External, unless this is
   restricted to a Google Workspace).
3. Create credentials → OAuth client ID → Application type **Web
   application**.
4. Add an **Authorized redirect URI** matching exactly where the
   frontend will send the user back to, e.g.
   `http://localhost:5173/auth/google/callback` for local dev.
5. Note the generated **Client ID** and **Client Secret**.

**Environment variables this app will read** (already reserved in
`.env.example`, not used until implemented):
```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/google/callback
```

**What the real implementation will do** (Phase 3 did not build this
part): the frontend redirects the user to Google's consent screen;
Google redirects back to `GOOGLE_REDIRECT_URI` with an authorization
code; the backend exchanges that code for an ID token via Google's
token endpoint; the backend **verifies the ID token's signature and
audience** using Google's public keys (the `google-auth` library) —
never trusts an unverified token handed to it directly; on success, it
looks up a `User` by the verified `sub` claim, creating one if it
doesn't exist yet, and issues this app's own JWT exactly the same way
`/login` does now.

## Requirements

- Python 3.11 or newer (developed and tested against 3.12)

## Setup — Windows (PowerShell)

```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

If PowerShell refuses to run the activation script, run this once in an
elevated PowerShell window, then retry:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Setup — Windows (Command Prompt)

```bat
cd backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

## Setup — macOS / Linux

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run the server

```bash
uvicorn app.main:app --reload
```

Then open:
- http://127.0.0.1:8000/ — basic service info
- http://127.0.0.1:8000/api/v1/health — health check
- http://127.0.0.1:8000/docs — interactive API docs (Swagger UI)

## Set up the database (Phase 2)

Creates `skincare.db` in the `backend/` folder with all current tables:

```bash
alembic upgrade head
```

To undo it (drops every table defined so far):

```bash
alembic downgrade base
```

After changing anything in `app/database/models.py`, generate a new
migration rather than editing the database by hand:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Run the tests

```bash
pytest -v
```

Expected result right now: **94 passed**.

## Project layout (through Phase 3)

```
backend/
  app/
    __init__.py
    main.py              FastAPI app, routes, CORS, error handling
    core/
      __init__.py
      config.py          All environment-driven settings, in one place
      security.py        Hashing, JWT, get_current_user, ensure_owner
    database/
      __init__.py
      connection.py      Engine, session factory, get_db dependency
      models.py           All ORM tables (not app/models/ — see note below)
    schemas/
      __init__.py
      auth_schema.py      Request/response shapes for auth
      profile_schema.py   Skin-profile shapes + concern validation
      journal_schema.py   Journal shapes + tag/date validation
      chat_schema.py      Chat request/response shapes
      acne_schema.py      Acne analysis response shape
      catalog_schema.py   Product/ingredient/routine/report shapes
    api/
      __init__.py
      auth.py             /auth/register, /login, /me, /logout
      profile.py          /profile (GET, PUT)
      journal.py          /journal CRUD
      chat.py             /chat + /chat/sessions
      acne.py             /acne/analyze (image upload)
      products.py         /products catalog (read-only)
      routines.py         /routines CRUD + /routines/{id}/log
      reports.py          /reports/summary
    services/
      __init__.py
      llm_service.py      LLMProvider interface + MockProvider + factory
      chat_service.py     orchestrates one chat turn
      safety_service.py   emergency/crisis screening + disclaimers
      acne_service.py     image validation + honest not-configured inference
    knowledge_base/
      skincare_faqs.json  curated, source-attributed FAQ entries
  alembic/                Migrations (one per schema change, in order)
  tests/
    __init__.py
    test_health.py
    test_database.py
    test_auth.py
    test_profile_journal.py
    test_chat.py
    test_acne.py
    test_products_routines_reports.py
  alembic.ini
  scripts/
    seed_demo_products.py
  requirements.txt
  .env.example
  .gitignore
  README.md
```

Naming note: ORM models live in `app/database/models.py`, not a
top-level `app/models/` — the acne classifier's checkpoint file
(Phase 6) will also want to be called "models," and keeping SQLAlchemy
tables under `database/` avoids two unrelated things sharing a name.

Phase 6 will add the acne-model inference service (and only then any
PyTorch dependency), when the real checkpoint is available to verify.

## Hardware notes for later phases (not relevant to Phase 1 yet)

Recorded here now so later phases don't have to rediscover it:

- **8 GB RAM, Intel CPU, NVIDIA MX350 with only 2 GB VRAM.** That VRAM
  figure rules out running any real local LLM on GPU — 2 GB isn't
  enough for even a small quantized model. The chatbot (Phase 5) will
  default to a hosted free-tier API, with the provider abstracted so a
  local model can be added later for CPU-only or a bigger machine.
- **CUDA 13.0 reported by the driver does not mean PyTorch will use the
  GPU.** The driver's CUDA version and the CUDA version PyTorch was
  *built against* are two different things. When the acne model (Phase
  6) is wired up, we will explicitly check `torch.cuda.is_available()`
  and the installed build before assuming GPU inference works, and will
  default to CPU inference if there's any doubt.
- **No large dependencies until they're actually needed.** PyTorch,
  Hugging Face, etc. are not installed in Phase 1 and won't be added
  until the phase that uses them.

## Design notes / why things are done this way

- **One settings object, read once.** `get_settings()` is cached, and
  everything in the app reads configuration through it rather than
  calling `os.environ` in multiple places. This is the single spot
  later phases (auth secrets, database URL, LLM provider keys) will
  extend.
- **CORS safety is enforced at startup, not just configured.** A
  wildcard origin combined with credentials is a real security
  footgun; the app raises a clear error immediately rather than
  starting in a broken or unsafe state.
- **Errors are centralized.** The global exception handler means no
  individual route has to remember to catch and sanitize errors —
  anything unexpected is logged in full on the server and reported
  generically to the client.
