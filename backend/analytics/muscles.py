"""Muscle Analysis (Phase 7).

Aggregates the Phase 2 normalized workout model through the deterministic
exercise -> primary-muscle mapping::

    List[WorkoutRecord]
            |
    compute_muscles (deterministic, no I/O, no randomness, no LLM,
                     no pandas -- the normalized model is sufficient)
            |
    MuscleAnalysisResponse (observed facts only -- no interpretation,
                            no recommendations)

Per canonical muscle:
- total_sets: every normalized set of every mapped exercise counts,
  regardless of set_type (consistent with total-set definitions).
  Unmapped exercises contribute to NO muscle total (never "Other").
- training_sessions: distinct workout occurrences containing >= 1 set of
  a mapped exercise of that muscle (at most 1 per workout per muscle).
- exercise_variety: distinct normalized exercise names mapped to the
  muscle and present in the dataset.
- average_sessions_per_week: training_sessions / (dataset period days / 7)
  using the global dataset span (Phase 3 calendar-period logic); None when
  the span is 0 days or unknown. Raw session counts are always returned.
- potentially_neglected: True ONLY when total_sets == 0. Unmapped
  exercises never imply a neglected muscle.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from data.models import WorkoutRecord
from mappings.exercise_muscles import PRIMARY_MUSCLES, get_primary_muscle


class MuscleSummary(BaseModel):
    """Aggregated facts for one canonical muscle."""

    muscle: str
    total_sets: int = 0
    training_sessions: int = 0
    exercise_variety: int = 0
    average_sessions_per_week: float | None = Field(
        default=None,
        description="Sessions per week over the dataset span; None if span is 0.",
    )
    potentially_neglected: bool = Field(
        default=False,
        description="True only when the muscle has zero mapped sets.",
    )


class MappingCoverage(BaseModel):
    """How much of the dataset the mapping table covers."""

    total_exercises: int = 0
    mapped_exercises: int = 0
    unmapped_exercises: int = 0
    coverage_percent: float = 0.0


class MuscleAnalysisResponse(BaseModel):
    """Muscle analysis: one summary per canonical muscle plus coverage."""

    muscles: list[MuscleSummary] = Field(default_factory=list)
    mapping: MappingCoverage = Field(default_factory=MappingCoverage)
    unmapped_exercises: list[str] = Field(
        default_factory=list,
        description="Alphabetical names missing from the mapping table.",
    )


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


def _dataset_period_days(workouts: list[WorkoutRecord]) -> int | None:
    """Calendar-day span of the whole dataset (Phase 3 period logic)."""
    starts = [
        s for s in (_parse_start(w.start_time) for w in workouts) if s is not None
    ]
    if not starts:
        return None
    return (max(starts).date() - min(starts).date()).days


def _distinct_exercise_names(workouts: list[WorkoutRecord]) -> list[str]:
    """Distinct non-empty normalized exercise names, sorted."""
    return sorted(
        {
            e.exercise_name
            for w in workouts
            for e in w.exercises
            if e.exercise_name and e.exercise_name.strip()
        }
    )


def compute_muscles(workouts: list[WorkoutRecord]) -> MuscleAnalysisResponse:
    """Aggregate muscle facts from normalized workouts via the mapping table."""
    names = _distinct_exercise_names(workouts)
    mapped = {n for n in names if get_primary_muscle(n) is not None}
    unmapped = sorted(set(names) - mapped)

    sets_per_muscle: dict[str, int] = {m: 0 for m in PRIMARY_MUSCLES}
    sessions_per_muscle: dict[str, set[int]] = {m: set() for m in PRIMARY_MUSCLES}
    variety_per_muscle: dict[str, set[str]] = {m: set() for m in PRIMARY_MUSCLES}

    for index, workout in enumerate(workouts):
        muscles_in_workout: set[str] = set()
        for exercise in workout.exercises:
            muscle = get_primary_muscle(exercise.exercise_name)
            if muscle is None:
                continue  # unmapped: excluded from every muscle total
            variety_per_muscle[muscle].add(exercise.exercise_name)
            muscles_in_workout.add(muscle)
            for _ in exercise.sets:
                sets_per_muscle[muscle] += 1
        for muscle in muscles_in_workout:
            sessions_per_muscle[muscle].add(index)

    period_days = _dataset_period_days(workouts)

    muscles: list[MuscleSummary] = []
    for muscle in sorted(PRIMARY_MUSCLES):
        total_sets = sets_per_muscle[muscle]
        sessions = len(sessions_per_muscle[muscle])
        if period_days is not None and period_days > 0:
            per_week: float | None = round(sessions / (period_days / 7), 2)
        else:
            per_week = None
        muscles.append(
            MuscleSummary(
                muscle=muscle,
                total_sets=total_sets,
                training_sessions=sessions,
                exercise_variety=len(variety_per_muscle[muscle]),
                average_sessions_per_week=per_week,
                potentially_neglected=total_sets == 0,
            )
        )

    total_exercises = len(names)
    mapped_count = len(mapped)
    coverage = (
        round(mapped_count / total_exercises * 100, 2)
        if total_exercises
        else 100.0
    )
    return MuscleAnalysisResponse(
        muscles=muscles,
        mapping=MappingCoverage(
            total_exercises=total_exercises,
            mapped_exercises=mapped_count,
            unmapped_exercises=len(unmapped),
            coverage_percent=coverage,
        ),
        unmapped_exercises=unmapped,
    )


__all__ = [
    "MuscleSummary",
    "MappingCoverage",
    "MuscleAnalysisResponse",
    "compute_muscles",
]
