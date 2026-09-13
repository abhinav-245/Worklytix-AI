"""Normalization (step 3 of the pipeline).

Responsibilities:
- Group cleaned rows into the Workout -> Exercise -> Set hierarchy.
- Compute basic dataset statistics (counts and data-quality info only --
  no analytics calculations).

Grouping rules (deterministic):
- A workout session is identified by (title, start_time). Rows sharing both
  belong to the same workout; one CSV row never becomes its own workout.
- Exercises keep their first-appearance order within a workout.
- Sets are ordered by set_index (rows with missing/invalid set_index go last,
  keeping their original relative order).
"""

from __future__ import annotations

import pandas as pd

from .cleaner import CleanedData
from .models import (
    DatasetStatistics,
    ExerciseRecord,
    SetRecord,
    WorkoutRecord,
)

#: Number of dropped rows included in the response (full counts still add up).
MAX_DROPPED_ROWS_SAMPLE = 20


def _iso(value: object) -> str | None:
    """Format a Timestamp as ISO 8601, or None for missing values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp) and pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def _num(value: object) -> int | float | None:
    """Convert a cleaned numeric cell (None/NaN/float) to JSON-safe output."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def _first_text(values: pd.Series) -> str | None:
    """First non-empty text value in a group, or None."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_set(row: pd.Series) -> SetRecord:
    set_index = _num(row["set_index"])
    return SetRecord(
        set_number=int(set_index) if set_index is not None else None,
        set_type=str(row["set_type"]),
        weight_kg=_num(row["weight_kg"]),
        reps=_num(row["reps"]),
        rpe=_num(row["rpe"]),
        distance_km=_num(row["distance_km"]),
        duration_seconds=_num(row["duration_seconds"]),
        extra=dict(row["extra"]) if isinstance(row["extra"], dict) else {},
    )


def build_workouts(frame: pd.DataFrame) -> list[WorkoutRecord]:
    """Group cleaned rows into workouts, exercises, and ordered sets."""
    if frame.empty:
        return []

    ordered = frame.sort_values(
        by=["start_time", "title"], kind="mergesort"
    )
    workouts: list[WorkoutRecord] = []

    for (title, start), group in ordered.groupby(
        ["title", "start_time"], sort=False
    ):
        exercises: list[ExerciseRecord] = []
        for exercise_name, ex_group in group.groupby(
            "exercise_title", sort=False
        ):
            sets = ex_group.sort_values(
                by=["set_index"], kind="mergesort", na_position="last"
            )
            exercises.append(
                ExerciseRecord(
                    exercise_name=str(exercise_name),
                    notes=_first_text(ex_group["exercise_notes"]),
                    superset_id=_first_text(ex_group["superset_id"]),
                    sets=[_build_set(row) for _, row in sets.iterrows()],
                )
            )
        end_times = group["end_time"].dropna()
        workouts.append(
            WorkoutRecord(
                title=str(title),
                description=_first_text(group["description"]),
                start_time=_iso(start) or "",
                end_time=_iso(end_times.iloc[0]) if not end_times.empty else None,
                exercises=exercises,
            )
        )
    return workouts


def compute_statistics(
    cleaned: CleanedData,
    workouts: list[WorkoutRecord],
    extra_columns: list[str],
) -> DatasetStatistics:
    """Compute dataset statistics from the cleaned frame and workouts."""
    frame = cleaned.frame
    valid_rows = len(frame)
    invalid_rows = len(cleaned.dropped_rows)
    total_sets = valid_rows

    starts = frame["start_time"].dropna() if not frame.empty else pd.Series([], dtype="datetime64[ns]")
    first_date = _iso(starts.min()) if not starts.empty else None
    last_date = _iso(starts.max()) if not starts.empty else None

    total_exercises = (
        int(frame["exercise_title"].nunique()) if not frame.empty else 0
    )

    return DatasetStatistics(
        total_rows=cleaned.total_rows,
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        total_workouts=len(workouts),
        total_exercises=total_exercises,
        total_sets=total_sets,
        first_workout_date=first_date,
        last_workout_date=last_date,
        missing_values=dict(cleaned.missing_values),
        invalid_values=dict(cleaned.invalid_values),
        extra_columns=list(extra_columns),
        dropped_rows=cleaned.dropped_rows[:MAX_DROPPED_ROWS_SAMPLE],
    )
