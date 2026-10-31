# Skincare.ai — combined project

```
backend/    FastAPI API (backend phase 7: auth, profile, journal, chat, acne, products, routines, reports)
frontend/   React + Vite + TypeScript (frontend phase 5: login, assessment, dashboard, journal, products, chatbot)
ml/         Acne model training scripts (optional; the API reports model_not_configured until a model is trained)
```

## Run

Backend (http://127.0.0.1:8000, docs at /docs):
```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit secrets
alembic upgrade head
python -m scripts.seed_demo_products   # optional demo products
python -m scripts.seed_dermacare_catalog   # optional: 1471-product searchable catalog
uvicorn app.main:app --reload
```

Frontend (http://localhost:5173):
```
cd frontend
npm install
copy .env.example .env      # VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
npm run dev
```

## Status
- Every backend endpoint now has a frontend screen (Acne Analysis, Reports and Routines were added in the merge).
- Backend: 171 tests pass (the test suite always runs against the mock LLM provider, regardless of your local `.env`). `python -m scripts.seed_demo_products` loads 33 generic sample products plus 98 brand products (DermaCare catalog: only the eligible, de-duplicated records; unverified candidates are never loaded). The Skin Assessment page then shows matched brand products (generic ones only as fallback) and a suggested morning/evening routine. Each product shows how much is known about its ingredients (verified / key ingredients only / not verified). When pregnancy caution, sensitivity or avoided ingredients are set, only brand products with a FULL ingredient list are screened and shown (highlights are not a complete list, so absence of an ingredient is never inferred); the generic samples fill in. Catalog files: `dermacare_catalog_improved.py` + `dermacare_products_improved.json`. Frontend: `npm run build` passes.
- Product search & browse (Products page): `python -m scripts.seed_dermacare_catalog` additionally loads a separate, much larger catalog (dermacare_products_searchable_categories.csv, 1471 products after dropping two rows that were just Excel `#NAME?` errors in the source file) into the same `products` table, independent of the assessment/recommendation engine above. The Products page search bar shows all 9 categories with live counts on focus (Sunscreen, Moisturizer, Cleanser, Toner & Essence, Serum & Treatment, Face Mask, Eye Care, Exfoliator & Peel, Spot Treatment), autocompletes as you type, and searches name/brand/ingredients case-insensitively via `GET /api/v1/products` (now also matching `ingredients_text`), `GET /api/v1/products/categories` and `GET /api/v1/products/count`. Raw ingredient text for this catalog is kept in a new `products.ingredients_text` column rather than exploded into `Ingredient` rows, so it doesn't affect the curated ingredient table the recommendation engine reads precaution text from.
- The acne endpoint returns `model_not_configured` until a model is trained from `ml/`; the page shows that honestly instead of a made-up result.

## AI agent
The Chat page can act as an agent that looks at your profile, journal, routines, reports and the
product catalog, and can propose creating/logging routines (you press **Confirm** - it never saves on its own).
Three providers are available, chosen with `LLM_PROVIDER` in `backend/.env`:

| `LLM_PROVIDER` | Where it runs | Needs |
|---|---|---|
| `mock` (default) | Nowhere - a fixed FAQ lookup | nothing |
| `ollama` | Your PC - chat text never leaves it | [Ollama](https://ollama.com/download) + `ollama pull qwen2.5:3b` |
| `gemini` | Google's cloud | a free key from [Google AI Studio](https://aistudio.google.com/apikey) in `GEMINI_API_KEY` |
| `groq` | Groq's cloud | a free key from [Groq Console](https://console.groq.com/keys) in `GROQ_API_KEY` |

With `gemini` or `groq`, set `LLM_FALLBACK_CHAIN=groq` (or `gemini`) to try a second provider if the
first fails for a given message; if every configured provider fails, the turn falls back to the
offline mock rather than erroring, and is always labelled so in the response (never shown as if an
AI generated it). Restart the backend after changing `.env`.

## Skin assessment & personalization
The Skin Assessment page is a 5-step wizard (personal info, skin type/subtype, sensitivity, concerns,
review) backed by a real reference dataset:
`backend/app/knowledge_base/dermacare_skin_assessment_dataset_binary.csv` (1120 rows - 5 age groups x
4 skin types x 2 subtypes each x 2 sensitivity states, every combination present, no gaps or
duplicates). `app/knowledge_base/skin_assessment_dataset.py` loads and indexes it; `app/services/
assessment_service.py` turns a saved profile into per-concern ingredient education without
duplicating the existing product-matching code in `recommendation_service.py`.

Endpoints (`backend/app/api/assessment.py`), all scoped to the authenticated caller:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/assessment` | Save a new assessment - upserts the live profile and appends an immutable history row |
| `GET /api/v1/assessment/me` | The current live profile (same row `/profile` reads, extended with age/age_group/skin_subtype/is_sensitive) |
| `PUT /api/v1/assessment/me` | Partial update of the live profile only (no new history row) |
| `GET /api/v1/assessment/history` | Past assessment snapshots, newest first |
| `GET /api/v1/assessment/profile` | Personalized ingredient-education output |
| `GET /api/v1/assessment/recommendations` | The above plus product/routine recommendations (delegates to the existing recommendation engine) |

Three things in the dataset turned out to differ from how it was first described, found by actually
inspecting the CSV rather than assuming: `Sensitivity` is literal `"Yes"`/`"No"` text, not `0`/`1`;
`Skin_Subtype` has exactly 2 real values per skin type (e.g. `"Extreme Dry"`, `"T-Zone Oily Cheeks
Dry"`), not the suggested 3-per-type labels; and `Concern` has 10 real categories, several different
from the ones first suggested (e.g. `"Open Pores"`, `"Dark Circles"`, `"Sun Tan"` exist, `"Fine
Lines"`/`"Large Pores"` don't). The code uses the dataset's real categories throughout. When a
subtype or sensitivity answer is missing, the engine shows guidance for every possibility rather than
guessing one.
