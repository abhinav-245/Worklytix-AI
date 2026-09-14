"""Exercise Volume Time Series (Phase 10).

Dedicated volume API over the Phase 2 normalized workout model::

    List[WorkoutRecord]
            |
    compute_volume (deterministic, no I/O, no randomness, no LLM,
                    no pandas -- the normalized model is sufficient)
            |
    VolumeResponse (observed facts only, chart-ready)

Definitions (consistent with existing analytics, never redefined):
- set volume = weight_kg x reps, using the Phase 4 eligibility rule
  (see analytics.prs.is_eligible_set): positive weight and positive
  integer reps, any set_type. Invalid sets are excluded, never zero-filled.
- occurrence volume = SUM of valid set volumes for one exercise within
  one workout (same definition as Phase 5 progression volume_kg, 2 dp).
  This is deliberately distinct from the Phase 4 volume PR, which is the
  maximum SINGLE-set volume.
- One point per exercise occurrence (same-day sessions stay separate),
  chronological by actual workout start datetimes. Occurrences without
  eligible sets produce no point; exercises without eligible sets get an
  empty history (never fake zeros).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from analytics.prs import is_eligible_set
from data.models import ExerciseRecord, WorkoutRecord


class VolumePoint(BaseModel):
    """Total exercise volume for one workout occurrence."""

    date: str = Field(description="Calendar date (YYYY-MM-DD) for charting.")
    workout_start: str = Field(
        description="Full ISO workout start; distinguishes same-day sessions."
    )
    volume_kg: float = Field(
        description="Sum of valid set volumes (weight x reps) in the workout."
    )


class ExerciseVolume(BaseModel):
    """Chronological volume history of one normalized exercise."""

    exercise_name: str
    history: list[VolumePoint] = Field(default_factory=list)


class VolumeResponse(BaseModel):
    """All exercise volume histories, sorted by exercise name."""

    exercises: list[ExerciseVolume] = Field(default_factory=list)


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


def _summarize_occurrence_volume(
    exercise: ExerciseRecord, start: datetime, start_raw: str
) -> VolumePoint | None:
    """Sum valid set volumes for one occurrence, or None if none are valid."""
    volumes = [
        float(s.weight_kg) * int(s.reps)  # type: ignore[arg-type]
        for s in exercise.sets
        if is_eligible_set(s.weight_kg, s.reps)
    ]
    if not volumes:
        return None
    return VolumePoint(
        date=start.date().isoformat(),
        workout_start=start_raw,
        volume_kg=round(sum(volumes), 2),
    )


def _exercise_volume_history(
    exercise_name: str, workouts: list[WorkoutRecord]
) -> list[VolumePoint]:
    """Chronological volume points for one exercise across all workouts."""
    dated: list[tuple[datetime, VolumePoint]] = []
    for workout in workouts:
        start = _parse_start(workout.start_time)
        if start is None:
            continue  # Phase 2 already drops these; never invent a date
        for exercise in workout.exercises:
            if exercise.exercise_name != exercise_name:
                continue
            point = _summarize_occurrence_volume(
                exercise, start, workout.start_time
            )
            if point is not None:
                dated.append((start, point))
    dated.sort(key=lambda item: item[0])
    return [point for _, point in dated]


def _all_exercise_names(workouts: list[WorkoutRecord]) -> list[str]:
    """Every distinct non-empty exercise name, sorted for stable output."""
    return sorted(
        {
            e.exercise_name
            for w in workouts
            for e in w.exercises
            if e.exercise_name and e.exercise_name.strip()
        }
    )


def compute_volume(workouts: list[WorkoutRecord]) -> VolumeResponse:
    """Build per-exercise volume histories from normalized workouts."""
    return VolumeResponse(
        exercises=[
            ExerciseVolume(
                exercise_name=name,
                history=_exercise_volume_history(name, workouts),
            )
            for name in _all_exercise_names(workouts)
        ]
    )


def compute_exercise_volume(
    workouts: list[WorkoutRecord], exercise_name: str
) -> ExerciseVolume | None:
    """Volume history for a single exercise, or None if unknown."""
    if exercise_name not in _all_exercise_names(workouts):
        return None
    return ExerciseVolume(
        exercise_name=exercise_name,
        history=_exercise_volume_history(exercise_name, workouts),
    )


__all__ = [
    "VolumePoint",
    "ExerciseVolume",
    "VolumeResponse",
    "compute_volume",
    "compute_exercise_volume",
]
