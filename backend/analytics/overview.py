"""Training Overview Analytics (Phase 3).

Consumes the Phase 2 normalized workout model::

    List[WorkoutRecord]
            |
    compute_overview (deterministic, no I/O, no randomness, no LLM)
            |
    TrainingOverview (facts only -- no judgments or recommendations)

Set-type accounting (canonical Phase 2 values):
    working_sets = set_type == "normal"
    warmup_sets  = set_type == "warm_up"
    dropsets     = set_type == "drop_set"
    failure_sets = set_type == "failure"
    other_sets   = anything else ("unknown", "unknown:<token>", ...)
    total_sets   = working + warmup + drops + failure + other

Definitions:
- training_period_days: calendar-date difference (last.date - first.date).
  Single workout (or single date) -> 0. No dates -> None.
- average_workout_duration_minutes: mean of valid (end - start) durations in
  minutes, rounded to 2 decimals. Missing end_time or end < start is excluded
  (never zero-filled, never clamped). None when no valid duration exists.
- workouts_per_week: total_workouts / (training_period_days / 7), rounded to
  2 decimals. None when the period is 0 days (single-date dataset) or unknown.
- training_consistency: percentage (0-100, rounded to 1 decimal) of ISO
  calendar weeks (Monday-Sunday) in the training span that contain >= 1
  workout. Observed weeks run from the Monday of the first workout's week to
  the Sunday of the last workout's week. None when no dated workouts exist.
  No target workouts/week is assumed.
- total_volume_kg: sum of valid set volumes (weight x reps, 2 dp) across
  the whole dataset, reusing the Phase 5/10 volume definition from
  analytics.volume (eligible sets only; bodyweight sets add nothing).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from analytics.volume import compute_total_volume
from data.models import WorkoutRecord


class TrainingOverview(BaseModel):
    """Deterministic training-overview facts for one normalized dataset."""

    total_workouts: int = 0
    training_period_days: int | None = Field(
        default=None,
        description="Calendar days between first and last workout (0 for one date).",
    )
    first_workout_date: str | None = None
    last_workout_date: str | None = None
    total_exercises: int = Field(
        default=0, description="Distinct non-empty normalized exercise names."
    )
    total_sets: int = 0
    working_sets: int = 0
    warmup_sets: int = 0
    dropsets: int = 0
    failure_sets: int = 0
    other_sets: int = Field(
        default=0,
        description="Sets with unrecognized set_type; in total_sets only.",
    )
    average_workout_duration_minutes: float | None = Field(
        default=None,
        description="Mean of valid workout durations; None if none are valid.",
    )
    workouts_per_week: float | None = Field(
        default=None,
        description="total_workouts / (training_period_days / 7); None if period is 0.",
    )
    training_consistency: float | None = Field(
        default=None,
        description="Percent of ISO calendar weeks in the span with >= 1 workout.",
    )
    total_volume_kg: float = Field(
        default=0.0,
        description="Total weighted volume (sum of valid set volumes, 2 dp).",
    )


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime defensively; unparseable/missing -> None."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _valid_starts(workouts: list[WorkoutRecord]) -> list[datetime]:
    """Start datetimes of workouts with a parseable start_time, in order."""
    starts = [_parse_dt(w.start_time) for w in workouts]
    return sorted(s for s in starts if s is not None)


def _count_set_types(workouts: list[WorkoutRecord]) -> dict[str, int]:
    counts = {
        "total": 0,
        "working": 0,
        "warmup": 0,
        "drops": 0,
        "failure": 0,
        "other": 0,
    }
    for workout in workouts:
        for exercise in workout.exercises:
            for s in exercise.sets:
                counts["total"] += 1
                if s.set_type == "normal":
                    counts["working"] += 1
                elif s.set_type == "warm_up":
                    counts["warmup"] += 1
                elif s.set_type == "drop_set":
                    counts["drops"] += 1
                elif s.set_type == "failure":
                    counts["failure"] += 1
                else:
                    counts["other"] += 1
    return counts


def _average_duration_minutes(workouts: list[WorkoutRecord]) -> float | None:
    """Mean of valid workout durations; None when none are valid."""
    durations: list[float] = []
    for workout in workouts:
        start = _parse_dt(workout.start_time)
        end = _parse_dt(workout.end_time)
        if start is None or end is None:
            continue  # missing duration: excluded, never zero-filled
        delta_minutes = (end - start).total_seconds() / 60
        if delta_minutes < 0:
            continue  # invalid (end before start): excluded, never clamped
        durations.append(delta_minutes)
    if not durations:
        return None
    return round(sum(durations) / len(durations), 2)


def _consistency(starts: list[datetime]) -> float | None:
    """Percent of ISO calendar weeks in the span containing >= 1 workout."""
    if not starts:
        return None
    first_date = min(starts).date()
    first_monday = first_date.fromordinal(
        first_date.toordinal() - first_date.weekday()
    )
    last_date = max(starts).date()
    observed_weeks = (last_date - first_monday).days // 7 + 1
    active_weeks = {
        (d.isocalendar().year, d.isocalendar().week) for d in (s.date() for s in starts)
    }
    return round(len(active_weeks) / observed_weeks * 100, 1)


def compute_overview(workouts: list[WorkoutRecord]) -> TrainingOverview:
    """Calculate the training overview from normalized workouts."""
    starts = _valid_starts(workouts)

    if starts:
        first, last = starts[0], starts[-1]
        period_days: int | None = (last.date() - first.date()).days
        first_iso: str | None = first.isoformat()
        last_iso: str | None = last.isoformat()
    else:
        period_days, first_iso, last_iso = None, None, None

    if period_days is not None and period_days > 0:
        workouts_per_week: float | None = round(
            len(workouts) / (period_days / 7), 2
        )
    else:
        workouts_per_week = None

    exercise_names = {
        e.exercise_name
        for w in workouts
        for e in w.exercises
        if e.exercise_name and e.exercise_name.strip()
    }
    counts = _count_set_types(workouts)

    return TrainingOverview(
        total_workouts=len(workouts),
        training_period_days=period_days,
        first_workout_date=first_iso,
        last_workout_date=last_iso,
        total_exercises=len(exercise_names),
        total_sets=counts["total"],
        working_sets=counts["working"],
        warmup_sets=counts["warmup"],
        dropsets=counts["drops"],
        failure_sets=counts["failure"],
        other_sets=counts["other"],
        average_workout_duration_minutes=_average_duration_minutes(workouts),
        workouts_per_week=workouts_per_week,
        training_consistency=_consistency(starts),
        total_volume_kg=compute_total_volume(workouts),
    )
