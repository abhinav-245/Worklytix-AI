"""Training Frequency Time Series.

Minimal deterministic dataset for the dashboard training-frequency chart
(Phase 11, spec section 16): per-ISO-week workout counts over the
normalized workout model::

    List[WorkoutRecord]
            |
    compute_training_frequency (deterministic, no I/O, no randomness,
                                no LLM, no pandas)
            |
    TrainingFrequencyResponse (observed facts only)

Definitions:
- One bucket per ISO calendar week (Monday-Sunday), spanning from the
  Monday of the first workout's week through the week containing the last
  workout. Weeks with no workouts are included with count 0 so charts
  render a continuous time axis.
- A workout counts toward the week containing its start_time.
- Chronological by actual datetimes; ISO year+week used together so
  December-January boundaries are correct.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from data.models import WorkoutRecord


class FrequencyWeek(BaseModel):
    """Workout count for one ISO calendar week."""

    week: str = Field(description="ISO week label, e.g. '2026-W02'.")
    week_start: str = Field(description="Monday date (YYYY-MM-DD).")
    workouts: int = Field(description="Workouts starting in this week.")


class TrainingFrequencyResponse(BaseModel):
    """Continuous weekly workout counts, oldest first."""

    weeks: list[FrequencyWeek] = Field(default_factory=list)


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


def _week_monday(start: datetime) -> datetime:
    """Monday 00:00 of the ISO week containing ``start``."""
    monday = start - timedelta(days=start.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def compute_training_frequency(
    workouts: list[WorkoutRecord],
) -> TrainingFrequencyResponse:
    """Bucket normalized workouts into continuous ISO-week counts."""
    starts = [
        s for s in (_parse_start(w.start_time) for w in workouts) if s is not None
    ]
    if not starts:
        return TrainingFrequencyResponse()

    counts: dict[tuple[int, int], int] = {}
    for start in starts:
        iso = start.isocalendar()
        key = (iso.year, iso.week)
        counts[key] = counts.get(key, 0) + 1

    first_monday = _week_monday(min(starts))
    last_start = max(starts)
    weeks: list[FrequencyWeek] = []
    cursor = first_monday
    while cursor <= last_start:
        iso = cursor.isocalendar()
        key = (iso.year, iso.week)
        weeks.append(
            FrequencyWeek(
                week=f"{key[0]}-W{key[1]:02d}",
                week_start=cursor.date().isoformat(),
                workouts=counts.get(key, 0),
            )
        )
        cursor += timedelta(days=7)
    return TrainingFrequencyResponse(weeks=weeks)


__all__ = [
    "FrequencyWeek",
    "TrainingFrequencyResponse",
    "compute_training_frequency",
]
