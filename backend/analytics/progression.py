"""Progression Analysis (Phase 5).

Builds per-exercise performance histories from the Phase 2 normalized
workout model::

    List[WorkoutRecord]
            |
    compute_progression (deterministic, no I/O, no randomness, no LLM,
                         no pandas -- the normalized model is sufficient)
            |
    ProgressionResponse (observed facts only -- no interpretation,
                         no judgments, no recommendations)

One progression point per exercise occurrence within a workout (never one
point per set, never merged across distinct same-day sessions):

    weight_kg        = max valid weight in the occurrence          (kg, 2 dp)
    reps             = max valid reps in the occurrence            (int)
    volume_kg        = SUM(weight x reps) over valid sets          (kg, 2 dp)
                       (differs deliberately from the Phase 4 volume PR,
                       which is the maximum SINGLE-set volume)
    estimated_1rm_kg = max Epley 1RM over valid sets               (kg, 2 dp)

Validity reuses the Phase 4 rule (see analytics.prs.is_eligible_set):
positive weight and positive integer reps, any set_type. Invalid sets are
excluded, never zero-filled. Occurrences without eligible sets produce no
point; exercises without eligible sets get an empty history (never fake
zeros). Histories sort oldest -> newest by actual workout start datetimes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from analytics.prs import calculate_estimated_1rm, is_eligible_set
from data.models import ExerciseRecord, WorkoutRecord


class ProgressionPoint(BaseModel):
    """Aggregated performance of one exercise in one workout occurrence."""

    date: str = Field(description="Calendar date (YYYY-MM-DD) for charting.")
    workout_start: str = Field(
        description="Full ISO workout start; distinguishes same-day sessions."
    )
    weight_kg: float = Field(description="Maximum valid weight in the workout.")
    reps: int = Field(description="Maximum valid reps in the workout.")
    volume_kg: float = Field(
        description="Total exercise volume (sum of set weight x reps)."
    )
    estimated_1rm_kg: float = Field(
        description="Maximum Epley estimated 1RM in the workout."
    )


class ExerciseProgression(BaseModel):
    """Chronological progression history of one normalized exercise."""

    exercise_name: str
    history: list[ProgressionPoint] = Field(default_factory=list)


class ProgressionResponse(BaseModel):
    """All exercise progression histories, sorted by exercise name."""

    exercises: list[ExerciseProgression] = Field(default_factory=list)


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


def _summarize_occurrence(
    exercise: ExerciseRecord, start: datetime, start_raw: str
) -> ProgressionPoint | None:
    """Aggregate one exercise occurrence into a point, or None if no valid sets."""
    weights: list[float] = []
    reps_list: list[int] = []
    volumes: list[float] = []
    epleys: list[float] = []
    for s in exercise.sets:
        if not is_eligible_set(s.weight_kg, s.reps):
            continue
        weight = float(s.weight_kg)  # type: ignore[arg-type]
        reps = int(s.reps)  # type: ignore[arg-type]
        weights.append(weight)
        reps_list.append(reps)
        volumes.append(weight * reps)
        epleys.append(calculate_estimated_1rm(weight, reps))
    if not weights:
        return None
    return ProgressionPoint(
        date=start.date().isoformat(),
        workout_start=start_raw,
        weight_kg=round(max(weights), 2),
        reps=max(reps_list),
        volume_kg=round(sum(volumes), 2),
        estimated_1rm_kg=round(max(epleys), 2),
    )


def _exercise_history(
    exercise_name: str, workouts: list[WorkoutRecord]
) -> list[ProgressionPoint]:
    """Chronological points for one exercise across all workouts."""
    dated: list[tuple[datetime, ProgressionPoint]] = []
    for workout in workouts:
        start = _parse_start(workout.start_time)
        if start is None:
            continue  # Phase 2 already drops these; never invent a date
        for exercise in workout.exercises:
            if exercise.exercise_name != exercise_name:
                continue
            point = _summarize_occurrence(exercise, start, workout.start_time)
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


def compute_progression(
    workouts: list[WorkoutRecord],
) -> ProgressionResponse:
    """Build per-exercise progression histories from normalized workouts."""
    return ProgressionResponse(
        exercises=[
            ExerciseProgression(
                exercise_name=name,
                history=_exercise_history(name, workouts),
            )
            for name in _all_exercise_names(workouts)
        ]
    )


def compute_exercise_progression(
    workouts: list[WorkoutRecord], exercise_name: str
) -> ExerciseProgression | None:
    """Progression history for a single exercise, or None if unknown."""
    if exercise_name not in _all_exercise_names(workouts):
        return None
    return ExerciseProgression(
        exercise_name=exercise_name,
        history=_exercise_history(exercise_name, workouts),
    )


__all__ = [
    "ProgressionPoint",
    "ExerciseProgression",
    "ProgressionResponse",
    "compute_progression",
    "compute_exercise_progression",
]
