"""Typed internal models for the Phase 2 CSV pipeline.

These models represent cleaned/normalized workout data only.
No analytics calculations belong here (those are Phase 3+).

Conceptual hierarchy::

    Workout
      -> Exercise
        -> Set
"""

from pydantic import BaseModel, Field


class SetRecord(BaseModel):
    """One normalized set within an exercise."""

    set_number: int | None = Field(
        default=None, description="Original set_index; None when missing/invalid."
    )
    set_type: str = Field(
        description=(
            "Normalized set type: 'normal', 'warm_up', 'drop_set', 'failure', "
            "'unknown' (empty source value) or 'unknown:<token>' (unrecognized value)."
        )
    )
    weight_kg: int | float | None = None
    reps: int | float | None = None
    rpe: int | float | None = None
    distance_km: int | float | None = None
    duration_seconds: int | float | None = None
    extra: dict[str, str] = Field(
        default_factory=dict,
        description="Non-empty values from unexpected CSV columns, preserved per row.",
    )


class ExerciseRecord(BaseModel):
    """One exercise (with its ordered sets) within a workout."""

    exercise_name: str
    notes: str | None = None
    superset_id: str | None = None
    sets: list[SetRecord] = Field(default_factory=list)


class WorkoutRecord(BaseModel):
    """One workout session."""

    title: str
    description: str | None = None
    start_time: str = Field(description="ISO 8601 datetime of the workout start.")
    end_time: str | None = Field(
        default=None, description="ISO 8601 datetime of the workout end, if known."
    )
    exercises: list[ExerciseRecord] = Field(default_factory=list)


class DroppedRow(BaseModel):
    """A source row excluded from the normalized dataset, with reasons."""

    row_number: int = Field(description="1-based CSV line number (header is line 1).")
    reasons: list[str] = Field(default_factory=list)


class DatasetStatistics(BaseModel):
    """Dataset-level statistics (NOT analytics)."""

    total_rows: int
    valid_rows: int
    invalid_rows: int
    total_workouts: int
    total_exercises: int = Field(
        description="Number of distinct exercise names in the dataset."
    )
    total_sets: int
    first_workout_date: str | None = None
    last_workout_date: str | None = None
    missing_values: dict[str, int] = Field(default_factory=dict)
    invalid_values: dict[str, int] = Field(default_factory=dict)
    extra_columns: list[str] = Field(default_factory=list)
    dropped_rows: list[DroppedRow] = Field(
        default_factory=list,
        description="Capped sample of excluded rows with reasons.",
    )


class UploadResponse(BaseModel):
    """Response body for POST /upload."""

    statistics: DatasetStatistics
    workouts: list[WorkoutRecord] = Field(default_factory=list)
