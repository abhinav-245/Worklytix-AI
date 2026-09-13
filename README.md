# Fitness Intelligence

A fitness-data analysis application that processes workout history, calculates
objective training metrics, presents patterns through a dashboard, and uses an
LLM to interpret those calculated results.

## Current Phase

Phase 3 — Training Overview Analytics

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
│   ├── main.py        # GET /health, POST /upload, GET /analysis/overview
│   ├── requirements.txt
│   ├── data/          # CSV pipeline: parser, cleaner, normalizer, models
│   ├── analytics/     # overview analytics (consumes normalized model only)
│   ├── tests/         # unittest suite + Hevy CSV fixture
│   ├── ai/            # (future phases)
│   └── mappings/      # (future phases)
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

## Notes

- Uploads are processed in memory; no database. Overview metrics are
  deterministic Python calculations over the normalized model — no LLM,
  no frontend calculations, no charts yet. PRs, volume, progression,
  plateaus, muscles, AI, and recommendations belong to later phases.
