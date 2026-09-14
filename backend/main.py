from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analytics.exercise_variety import (
    ExerciseVarietyAnalysis,
    compute_exercise_variety,
    compute_single_exercise_variety,
)
from analytics.muscles import MuscleAnalysisResponse, compute_muscles
from analytics.overview import TrainingOverview, compute_overview
from analytics.profile import (
    ProfileAnalysis,
    UserProfile,
    attach_bodyweight_ratios,
    compute_training_history,
)
from analytics.plateau import (
    PlateauResponse,
    compute_exercise_plateaus,
    compute_plateaus,
)
from analytics.prs import ExercisePR, generate_exercise_prs
from analytics.progression import (
    ProgressionResponse,
    compute_exercise_progression,
    compute_progression,
)
from data.models import UploadResponse, WorkoutRecord
from data.parser import CSVPipelineError, MissingColumnsError
from data.pipeline import process_csv_bytes

app = FastAPI(title="Fitness Intelligence API")

# Development CORS: allow local Next.js dev server.
# Easy to extend later via environment variables if needed.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


class UploadWithOverview(UploadResponse):
    """Phase 2 upload response plus Phase 3 overview facts (no extra parsing)."""

    overview: TrainingOverview | None = None


# In-memory V1 state: normalized workouts from the most recent upload.
# No database by design; per-process memory (a multi-worker deployment would
# need shared state later). Reset on restart; 404 until the first upload.
_LAST_WORKOUTS: list[WorkoutRecord] | None = None

# In-memory V1 user profile (no database, no persistence across restarts).
_LAST_PROFILE: UserProfile | None = None


@app.post("/upload", response_model=UploadWithOverview)
async def upload(file: UploadFile = File(...)):
    """Accept a workout CSV (multipart form data) and run the Phase 2 pipeline.

    The file is processed in memory; nothing is persisted.
    """
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": "A .csv file must be uploaded using multipart form data.",
            },
        )

    data = await file.read()
    try:
        result = process_csv_bytes(data)
    except MissingColumnsError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_columns",
                "message": exc.message,
                "missing_columns": exc.missing,
            },
        ) from exc
    except CSVPipelineError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_csv", "message": exc.message},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": "The CSV could not be processed due to a server error.",
            },
        ) from exc

    global _LAST_WORKOUTS
    _LAST_WORKOUTS = result.workouts
    overview = compute_overview(result.workouts)
    return UploadWithOverview(
        statistics=result.statistics, workouts=result.workouts, overview=overview
    )


@app.get("/analysis/overview", response_model=TrainingOverview)
def analysis_overview():
    """Overview facts for the most recently uploaded dataset (in-memory)."""
    if _LAST_WORKOUTS is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_dataset",
                "message": "No workout dataset has been uploaded yet. "
                "POST a CSV to /upload first.",
            },
        )
    return compute_overview(_LAST_WORKOUTS)


@app.get("/analysis/prs", response_model=list[ExercisePR])
def analysis_prs():
    """Per-exercise PR facts for the most recently uploaded dataset.

    When a profile with body weight exists, bodyweight-relative ratios are
    attached (backend-calculated); otherwise the ratio fields stay null.
    """
    if _LAST_WORKOUTS is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_dataset",
                "message": "No workout dataset has been uploaded yet. "
                "POST a CSV to /upload first.",
            },
        )
    prs = generate_exercise_prs(_LAST_WORKOUTS)
    if _LAST_PROFILE is not None:
        prs = attach_bodyweight_ratios(prs, _LAST_PROFILE.body_weight_kg)
    return prs


@app.post("/profile", response_model=ProfileAnalysis, status_code=200)
def submit_profile(profile: UserProfile) -> ProfileAnalysis:
    """Validate and store the V1 user profile in memory.

    Accepted independently of CSV upload; training history is null until
    workouts exist. Invalid input returns 422 (never silently corrected).
    """
    global _LAST_PROFILE
    _LAST_PROFILE = profile
    history = (
        compute_training_history(_LAST_WORKOUTS)
        if _LAST_WORKOUTS is not None
        else None
    )
    return ProfileAnalysis(profile=profile, training_history=history)


def _require_dataset() -> list[WorkoutRecord]:
    """Return the in-memory uploaded dataset or raise the 404 used by analysis."""
    if _LAST_WORKOUTS is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_dataset",
                "message": "No workout dataset has been uploaded yet. "
                "POST a CSV to /upload first.",
            },
        )
    return _LAST_WORKOUTS


@app.get("/analysis/progression", response_model=ProgressionResponse)
def analysis_progression(
    exercise_name: str | None = None,
) -> ProgressionResponse:
    """Chronological per-exercise progression for the uploaded dataset.

    Optionally filter to one normalized exercise with
    ``?exercise_name=...`` (exact match; 404 when unknown).
    """
    workouts = _require_dataset()
    if exercise_name is not None:
        single = compute_exercise_progression(workouts, exercise_name)
        if single is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_exercise",
                    "message": f"No exercise named {exercise_name!r} "
                    "in the uploaded dataset.",
                },
            )
        return ProgressionResponse(exercises=[single])
    return compute_progression(workouts)


@app.get("/analysis/plateaus", response_model=PlateauResponse)
def analysis_plateaus(
    exercise_name: str | None = None,
) -> PlateauResponse:
    """Possible-plateau periods for the uploaded dataset.

    Optionally filter to one normalized exercise with
    ``?exercise_name=...`` (exact match; 404 when unknown).
    """
    workouts = _require_dataset()
    if exercise_name is not None:
        known = any(
            e.exercise_name == exercise_name
            for w in workouts
            for e in w.exercises
        )
        if not known:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_exercise",
                    "message": f"No exercise named {exercise_name!r} "
                    "in the uploaded dataset.",
                },
            )
        return PlateauResponse(
            plateaus=compute_exercise_plateaus(workouts, exercise_name)
        )
    return compute_plateaus(workouts)


@app.get("/analysis/muscles", response_model=MuscleAnalysisResponse)
def analysis_muscles() -> MuscleAnalysisResponse:
    """Muscle-level aggregation for the uploaded dataset via the mapping table."""
    return compute_muscles(_require_dataset())


@app.get("/analysis/exercise-variety", response_model=ExerciseVarietyAnalysis)
def analysis_exercise_variety(
    exercise_name: str | None = None,
) -> ExerciseVarietyAnalysis:
    """Exercise-selection facts for the uploaded dataset.

    Optionally filter to one normalized exercise with
    ``?exercise_name=...`` (exact match; 404 when unknown).
    """
    workouts = _require_dataset()
    if exercise_name is not None:
        single = compute_single_exercise_variety(workouts, exercise_name)
        if single is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_exercise",
                    "message": f"No exercise named {exercise_name!r} "
                    "in the uploaded dataset.",
                },
            )
        return single
    return compute_exercise_variety(workouts)
