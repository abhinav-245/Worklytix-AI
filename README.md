# Fitness Intelligence

A fitness-data analysis application that processes workout history, calculates
objective training metrics, presents patterns through a dashboard, and uses an
LLM to interpret those calculated results.

## Current Phase

Phase 8 — Exercise Variety

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

## Project structure

```text
FIT-INTEL/
├── frontend/        # Next.js + TypeScript + Tailwind + shadcn/ui
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── .env.example
├── backend/         # FastAPI
│   ├── .venv/
│   ├── main.py        # /health, /upload, /analysis/* endpoints
│   ├── requirements.txt
│   ├── data/          # CSV pipeline: parser, cleaner, normalizer, models
│   ├── analytics/     # overview, PRs, progression, plateaus, muscles, variety
│   ├── tests/         # unittest suite + Hevy CSV fixture
│   ├── ai/            # (future phases)
│   └── mappings/      # exercise → primary-muscle mapping table
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

Open <http://localhost:3000>. The placeholder page shows
“Backend status” and calls `GET /health` using `NEXT_PUBLIC_API_URL`,
plus an upload card that posts a Hevy CSV to `POST /upload` and shows
the returned dataset statistics.

### 6. Run the backend tests

From the `backend/` directory, with the virtual environment activated:

```bash
cd backend
python -m unittest discover -s tests -v
```

## API

- `GET /health` → `{ "status": "ok" }`
- `POST /upload` (multipart form data, field `file`, `.csv` only) →
  `{ "statistics": {...}, "workouts": [...], "overview": {...} }` with the
  normalized Workout → Exercise → Set hierarchy, dataset statistics
  (`total_rows`, `valid_rows`, `invalid_rows`, `total_workouts`,
  `total_exercises`, `total_sets`, first/last workout dates,
  `missing_values`, `invalid_values`), and the training-overview facts.
  Invalid files return HTTP 400 with a JSON error; server failures return
  HTTP 500 without tracebacks.
- `GET /analysis/overview` → training-overview facts for the most recently
  uploaded dataset (in-memory; HTTP 404 `no_dataset` before the first upload).
- `GET /analysis/prs` → per-exercise PR facts for the most recently uploaded
  dataset (in-memory; HTTP 404 `no_dataset` before the first upload).
  Each entry: `exercise_name`, `weight_pr`, `rep_pr`, `volume_pr`,
  `estimated_1rm_pr` (each with `value`, `unit`, `date`, and — for volume/1RM
  — the `weight`/`reps` of the winning set; `null` when the exercise has no
  eligible sets).
- `GET /analysis/progression` → chronological per-exercise progression
  histories (`{ exercises: [{ exercise_name, history: [...] }] }`, sorted by
  exercise name; each point has `date`, `workout_start`, `weight_kg`, `reps`,
  `volume_kg`, `estimated_1rm_kg`). Optional `?exercise_name=...` filter
  (exact match; 404 `unknown_exercise` when absent). 404 `no_dataset` before
  the first upload. The frontend renders weight/rep/volume/estimated-1RM
  line charts per selected exercise.
- `GET /analysis/plateaus` → possible-plateau periods
  (`{ plateaus: [...] }`, sorted by exercise name then start; each with
  `label: "Possible Plateau"`, `plateau_start/end`, `duration_days`,
  `consecutive_weeks`, `heaviest_weight_kg`, `reps_at_heaviest_weight`,
  and per-week `evidence`). Optional `?exercise_name=...` filter.
  404 `no_dataset` before the first upload.
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

## Notes

- Uploads are processed in memory; no database. Overview, PR, progression,
  plateau, muscle, and variety metrics are deterministic Python calculations
  over the normalized model — no LLM, no frontend calculations. AI and
  recommendations belong to later phases.
