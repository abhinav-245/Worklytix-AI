# Fitness Intelligence

A fitness-data analysis application that processes workout history, calculates
objective training metrics, presents patterns through a dashboard, and uses an
LLM to interpret those calculated results.

## Current Phase

Phase 12 — AI Interpretation (Gemini 2.5 Flash, grounded in deterministic analytics)

## Technology

Frontend:

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

Backend:

- Python
- FastAPI
- Uvicorn
- Pandas (CSV pipeline)
- python-multipart (file uploads)
- httpx (backend tests only, via FastAPI TestClient)
- google-genai (Gemini 2.5 Flash AI interpretation; server-side only)

## Project structure

```text
FIT-INTEL/
├── frontend/        # Next.js + TypeScript + Tailwind + shadcn/ui
│   ├── app/
│   ├── components/
│   ├── lib/           # typed API client (lib/api.ts) + utils
│   └── .env.example
├── backend/         # FastAPI
│   ├── .venv/
│   ├── main.py        # /health, /upload, /profile, /analysis/* endpoints
│   ├── requirements.txt
│   ├── data/          # CSV pipeline: parser, cleaner, normalizer, models
│   ├── analytics/     # overview, PRs, progression, volume, plateaus, muscles, variety, profile
│   ├── ai/            # Phase 12: Gemini interpretation (context, prompts, service, validation)
│   ├── api/           # standardized {success, data, meta} envelope models
│   ├── tests/         # unittest suite + Hevy CSV fixture
│   ├── mappings/      # exercise → primary-muscle mapping table
├── README.md
└── .gitignore
```

## Running locally

Expected local URLs:

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>
- Backend health: <http://localhost:8000/health>

### 1. Create the backend virtual environment

From the repository root:

Windows (PowerShell):

```powershell
python -m venv backend/.venv
```

macOS/Linux:

```bash
python3 -m venv backend/.venv
```

### 2. Activate the backend virtual environment

Windows (PowerShell):

```powershell
backend/.venv/Scripts/Activate.ps1
```

Windows (cmd):

```bat
backend\.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
source backend/.venv/bin/activate
```

### 3. Install backend dependencies

Python dependencies must be installed **only inside the virtual environment**.
Verify `python -c "import sys; print(sys.executable)"` points to `backend/.venv/`
before installing.

```bash
python -m pip install -r backend/requirements.txt
```

### 4. Start the backend

From the `backend/` directory, with the virtual environment activated:

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{ "status": "ok" }
```

### 5. Start the frontend

In a separate terminal, from the repository root:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>. The landing page explains the product and
offers unified onboarding: Hevy CSV plus age, body weight and goal in one
Get Started card with a single Upload & Analyze action. After processing,
the app navigates to the compact Overview; dedicated routes serve PRs,
progression, volume, plateaus, muscles, exercises and profile — all
through the typed client in `frontend/lib/api.ts` from
`NEXT_PUBLIC_API_URL`.

## Dashboard

The V1 product (gold/black glass theme, dark-first) flows as
landing → Upload & Analyze → Overview → dedicated routes:

- **Landing (`/`)**: hero, Get Started card (CSV drop zone + age +
  body weight + goal + Upload & Analyze), concise value props. Upload
  posts CSV, then profile, then navigates to Overview; errors allow
  retry without a separate profile step.
- **Header**: sticky glass bar with FIT-INTEL branding, route nav
  (Home, Overview, PR, Progression, Volume, Plateau, Insights, More),
  gold active state, Get Started CTA, dataset status pill and mobile
  menu.
- **Overview (`/overview`)**: four cards only — Days Trained, Total
  Sets, Total Weighted Volume (`total_volume_kg` from the overview API),
  Experience (observed training-history level).
- **PR (`/pr`)**, **Progression (`/progression`)**, **Volume (`/volume`)**,
  **Plateau (`/plateau`)**, **Muscles (`/muscles`)**,
  **Exercises (`/exercises`)**, **Profile (`/profile`)**: existing
  section components behind routes with isolated loading/error/empty
  states and per-section retry.
- **Insights (`/insights`)**: Coming Soon placeholder; no AI exists yet.

No analytics are calculated in the frontend; charts only visualize
backend values.

### 6. Run the backend tests

From the `backend/` directory, with the virtual environment activated:

```bash
cd backend
python -m unittest discover -s tests -v
```

## API

Every analytics endpoint shares one contract (Phase 10):

```json
{
  "success": true,
  "data": { "...endpoint-specific payload..." },
  "meta": { "analysis_version": "v1" }
}
```

- `data` keeps each endpoint's established domain shape (progression keeps
  `{exercises: [...]}`; PRs use `{exercises: [...]}`).
- `meta` carries only the version string — analytics never depend on time.
- Missing dataset → HTTP 404 `no_dataset`; missing profile →
  404 `no_profile`; unknown `?exercise_name=` → 404 `unknown_exercise`;
  invalid request bodies keep FastAPI's standard 422 responses.
- Interactive docs: `/docs`; machine contract: `/openapi.json`.

Endpoints:

- `POST /upload`, `POST /profile` (unenveloped, unchanged behavior)
- `GET /analysis/overview`
- `GET /analysis/prs`
- `GET /analysis/progression` (+ optional `?exercise_name=`)
- `GET /analysis/volume` → per-exercise total-volume time series
  (`{exercises: [{exercise_name, history: [{date, workout_start,
  volume_kg}]}]}`); workout-level `Σ weight × reps`, matching Phase 5
  progression volume — distinct from the Phase 4 single-set volume PR.
  Optional `?exercise_name=` filter.
- `GET /analysis/frequency` → continuous ISO-week workout counts
  (`{weeks: [{week, week_start, workouts}]}`), including zero-weeks.
- `GET /analysis/plateaus` (+ optional `?exercise_name=`)
- `GET /analysis/muscles`
- `GET /analysis/exercise-variety` (+ optional `?exercise_name=`)
- `GET /analysis/profile` → `{profile, training_history}` (404
  `no_profile` before submission; `training_history: null` before upload)

The frontend consumes these through the typed client in
`frontend/lib/api.ts`, which unwraps `data` and returns `null` when no
result exists. Components receive the same domain shapes as before.

- `POST /upload` (multipart form data, field `file`, `.csv` only) →
  `{ "statistics": {...}, "workouts": [...], "overview": {...} }` with the
  normalized Workout → Exercise → Set hierarchy and dataset statistics.
  Invalid files return HTTP 400 with a JSON error; server failures return
  HTTP 500 without tracebacks.
- `GET /analysis/muscles` → muscle aggregation
  (`{ muscles: [...], mapping: {...}, unmapped_exercises: [...] }`): per
  canonical muscle `total_sets`, `training_sessions`, `exercise_variety`,
  `average_sessions_per_week`, `potentially_neglected`; plus mapping
  coverage and the alphabetical unmapped-exercise list.
  404 `no_dataset` before the first upload. The frontend shows a table,
  a sets-per-muscle bar chart, coverage, neglected muscles, and unmapped
  names.
- `GET /analysis/exercise-variety` → exercise-selection facts
  (`{ total_workouts, distinct_exercises, exercises, frequencies,
  exercises_per_muscle, selection_events, selection_summary }`): per-exercise
  `workout_occurrences`, `frequency_percent` (denominator = total workouts),
  `rarely_performed` (≤10%), `frequently_performed` (≥50%), and
  `introduced`/`disappeared`/`reappeared` ISO-week events (training weeks
  only — global gaps create no events). Optional `?exercise_name=...`
  filter. 404 `no_dataset` before the first upload. The frontend shows
  counts, per-muscle variety, a top-exercises bar chart, the frequency
  table, rare/frequent lists, and the event timeline.

## Profile, bodyweight & experience

- Profile fields: `age` (integer, 1–120), `body_weight_kg` (kg, >0, ≤1000,
  decimals preserved), `goal` (`muscle_gain`, `strength`, `fat_loss`,
  `general_fitness` — context only, no recommendations). Stored in memory;
  no database, no auth, no persistence.
- Training history uses earliest/latest normalized workout calendar dates
  (never today): `duration_days`, deterministic calendar `duration_text`
  (e.g. "2 years, 3 months, 19 days"), and the observed-duration level:
  Beginner (<1 year), Intermediate (1 to <3 years), Advanced (≥3 years).
  The level describes **observed data duration, not athletic ability**.
- Load/bodyweight ratios (`load / body_weight_kg`, 2 dp) are derived
  metadata attached to PR records; original loads are never overwritten,
  and missing PRs keep null ratios.

## Exercise variety

- Frequency counts distinct workouts containing the exercise (duplicates
  within one workout count once); unmapped exercises keep full
  exercise-level statistics but contribute to no muscle bucket.
- Selection events are observational only: first presence → `introduced`,
  present → absent → `disappeared`, absent → present → `reappeared`. They
  imply no reason and no recommendation.

## Muscle mapping

- Deterministic exact-match `exercise → primary muscle` table
  (`backend/mappings/exercise_muscles.py`); one primary muscle per
  exercise, no secondary muscles, no AI. Unknown exercises → `null`
  (reported in `unmapped_exercises`, never "Other", never a neglected
  muscle).
- Per muscle: every normalized set of mapped exercises counts (all set
  types); sessions = distinct workouts with ≥1 mapped set (max 1 per
  workout); variety = distinct mapped exercise names present.
- A canonical muscle with zero mapped sets is `Potentially Neglected`
  (conservative baseline only — no scoring, no recommendations).

## Plateau detection

- An exercise occurrence is reduced to (heaviest valid weight, max reps at
  that weight); each ISO week (Monday–Sunday) takes its best weekly
  signature. The same signature across **4+ consecutive performance weeks**
  (a missing week breaks the run) yields one `Possible Plateau` record with
  `consecutive_weeks`, observed `plateau_start/end` dates, `duration_days`,
  and per-week evidence. Longer runs extend one record; separate runs stay
  separate. Same Phase 4 validity rule, any `set_type`; no AI, no advice.

## Progression analysis

- One point per exercise occurrence within a workout (same-day sessions stay
  separate; ordered oldest → newest by workout start time).
- Per point: max weight, max reps, **total** exercise volume
  (`Σ weight × reps` — deliberately different from the Phase 4 single-set
  volume PR), max Epley estimated 1RM (2 dp).
- Same Phase 4 validity rule (positive weight + positive integer reps, any
  `set_type`); invalid sets excluded, never zero-filled; exercises without
  eligible sets get an empty history.

## PR engine

- Weight PR: heaviest eligible `weight_kg` (kg, 2 dp).
- Rep PR: highest eligible `reps` (int).
- Volume PR: highest single-set `weight_kg × reps` (kg, 2 dp).
- Estimated 1RM: Epley formula `weight × (1 + reps / 30)` (kg, 2 dp);
  Estimated 1RM PR is its maximum — the heaviest set does not always win.
- Eligibility: any set with valid positive weight and positive integer reps,
  regardless of `set_type`. Missing/invalid/zero/negative values are never
  zero-filled or inferred; such sets are ineligible. Ties resolve to the
  earliest occurrence.

## AI interpretation (Gemini 2.5 Flash)

- `POST /ai/ask` answers training questions using Gemini 2.5 Flash
  (`google-genai` 2.x SDK, `models.generate_content` with a JSON
  `response_schema`). No analytics are calculated by the LLM or the
  frontend; every number comes from the deterministic engines.
- Server-side key only: `backend/.env` holds `GEMINI_API_KEY` (and
  optional `GEMINI_MODEL`, default `gemini-2.5-flash`). Placeholders live
  in `backend/.env.example` — never a real key. `.env` is git-ignored.
  The key is never sent to the frontend, never logged, and the frontend
  has no `NEXT_PUBLIC_*` key variable.
- Each request rebuilds a compact versioned analytics context from the
  live dataset/profile (summaries always; per-point detail only for
  exercises named in the question). The raw CSV is never sent.
- Every context fact gets a stable backend-generated ID (e.g.
  `pr:bench_press_barbell:weight_pr`); observations must cite valid IDs,
  and measured values in factual statements must appear in the context.
  Violations trigger one corrective retry, then a controlled error.
- Responses distinguish `answer`, grounded `observations`, `assumptions`
  (possible but unproven) and `limitations` (unavailable data such as
  nutrition, sleep or recovery — reported as unavailable, never invented).
- Errors: `no_dataset` (404), `ai_not_configured` (503),
  `ai_provider_error` (502); invalid questions keep FastAPI 422s.
- Ask My Training lives on `/insights` (suggested questions, chat with
  loading/error states, session-only history, max 20 turns).
- AI does not replace deterministic analytics and makes no autonomous
  recommendations.

## Notes

- Uploads and profiles live in memory; no database. Overview, PR,
  progression, volume, plateau, muscle, variety, and profile metrics are
  deterministic Python calculations over the normalized model — no LLM, no
  frontend calculations. The analytics API wraps them in a versioned
  `{success, data, meta}` envelope for the dashboard and the AI layer.
  AI interpretation is grounded in those analytics; autonomous
  recommendations belong to later phases.

## Browser UI verification

Reusable Playwright + Chromium smoke test for the rendered Next.js UI.

- Setup (one time, from `frontend/`): `npm install` then
  `npx playwright install chromium`. Playwright uses its own Chromium
  build, independent of any installed Chrome.
- Normal command (from `frontend/`): `npm run test:e2e`. The config
  reuses `http://localhost:3000` when already running, otherwise starts
  `next dev` automatically via `webServer`.
- Headed/debug: `npm run test:e2e:headed` (visible browser),
  `npm run test:e2e:ui` (interactive Playwright UI mode).
- Smoke suite: `frontend/e2e/ui-smoke.spec.ts` (homepage, header/menu,
  onboarding entry, routes incl. `/profile` 404, dropdown usability,
  mobile 375x812, console/page/network errors, checkpoint screenshots).
- Failure evidence: `frontend/test-results/` (screenshots) plus traces
  retained on failure (`playwright.config.ts`: `trace:
  retain-on-failure`, `screenshot: only-on-failure`).
- Future UI phases: run `npm run test:e2e` after UI changes; extend with
  focused per-phase specs rather than growing the smoke suite.
