"""Exercise Variety Analysis (Phase 8).

Analyzes exercise-selection patterns from the Phase 2 normalized model::

    List[WorkoutRecord]
            |
    compute_exercise_variety (deterministic, no I/O, no randomness, no LLM,
                              no pandas -- the normalized model is sufficient)
            |
    ExerciseVarietyAnalysis (observed facts only -- no interpretation,
                             no recommendations, no scoring)

Definitions:
- Occurrence: an exercise counts at most once per workout (duplicate
  records/sets within one workout do not inflate frequency).
- frequency_percent = workout_occurrences / total_workouts * 100 (2 dp).
- Rarely Performed: frequency_percent <= 10. Frequently Performed:
  frequency_percent >= 50. Between the thresholds: neither.
- Selection history uses ISO calendar weeks (Monday-Sunday). Only weeks
  containing at least one workout are analyzed, so global training gaps
  never fabricate disappearance/reappearance events.
- Events: introduced (first ever presence week), disappeared
  (present -> absent), reappeared (absent -> present). Dates are observed
  dates only: for introduced/reappeared the exercise's first date that
  week; for disappeared the week's first training date.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from data.models import WorkoutRecord
from mappings.exercise_muscles import get_primary_muscle

#: Frequency at or below which an exercise is Rarely Performed.
RARELY_PERFORMED_MAX_PERCENT = 10.0

#: Frequency at or above which an exercise is Frequently Performed.
FREQUENTLY_PERFORMED_MIN_PERCENT = 50.0

SelectionEventType = Literal["introduced", "disappeared", "reappeared"]


class ExerciseFrequency(BaseModel):
    """How often one exercise appears across distinct workouts."""

    exercise_name: str
    muscle: str | None = Field(
        default=None, description="Phase 7 primary muscle; None if unmapped."
    )
    workout_occurrences: int
    frequency_percent: float
    rarely_performed: bool = False
    frequently_performed: bool = False


class MuscleExerciseCount(BaseModel):
    """Distinct mapped exercises belonging to one muscle."""

    muscle: str
    exercise_count: int


class ExerciseSelectionEvent(BaseModel):
    """One observational selection change for one exercise."""

    exercise_name: str
    event_type: SelectionEventType
    week: str = Field(description="ISO week label, e.g. '2025-W12'.")
    date: str = Field(description="Observed date (YYYY-MM-DD) for the event.")


class SelectionSummary(BaseModel):
    """Counts of selection events by type."""

    total_selection_events: int = 0
    introductions: int = 0
    disappearances: int = 0
    reappearances: int = 0


class ExerciseVarietyAnalysis(BaseModel):
    """Exercise-selection facts for the uploaded dataset."""

    total_workouts: int = 0
    distinct_exercises: int = 0
    exercises: list[str] = Field(
        default_factory=list, description="Alphabetical distinct names."
    )
    frequencies: list[ExerciseFrequency] = Field(default_factory=list)
    exercises_per_muscle: list[MuscleExerciseCount] = Field(default_factory=list)
    selection_events: list[ExerciseSelectionEvent] = Field(default_factory=list)
    selection_summary: SelectionSummary = Field(default_factory=SelectionSummary)


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


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


def _exercise_workout_indexes(
    exercise_name: str, workouts: list[WorkoutRecord]
) -> set[int]:
    """Workout positions containing the exercise (at most once per workout)."""
    return {
        index
        for index, workout in enumerate(workouts)
        for exercise in workout.exercises
        if exercise.exercise_name == exercise_name
    }


def _training_weeks(
    workouts: list[WorkoutRecord],
) -> list[tuple[int, int]]:
    """Sorted ISO (year, week) keys of weeks containing >= 1 workout."""
    weeks: set[tuple[int, int]] = set()
    for workout in workouts:
        start = _parse_start(workout.start_time)
        if start is None:
            continue  # Phase 2 already drops these; never invent a date
        iso = start.isocalendar()
        weeks.add((iso.year, iso.week))
    return sorted(weeks)


def _week_label(year: int, week: int) -> str:
    """ISO week label, e.g. '2025-W12'."""
    return f"{year}-W{week:02d}"


def _exercise_presence_by_week(
    exercise_name: str,
    workouts: list[WorkoutRecord],
    weeks: list[tuple[int, int]],
) -> dict[tuple[int, int], list[datetime]]:
    """Map each training week to the exercise's occurrence datetimes there."""
    presence: dict[tuple[int, int], list[datetime]] = {w: [] for w in weeks}
    for workout in workouts:
        start = _parse_start(workout.start_time)
        if start is None:
            continue
        iso = start.isocalendar()
        key = (iso.year, iso.week)
        if any(
            e.exercise_name == exercise_name for e in workout.exercises
        ):
            presence[key].append(start)
    return presence


def _week_first_training_date(
    year: int, week: int, workouts: list[WorkoutRecord]
) -> str:
    """Earliest workout date in an ISO week (for disappeared events)."""
    dates = [
        start.date().isoformat()
        for workout in workouts
        if (start := _parse_start(workout.start_time)) is not None
        and (start.isocalendar().year, start.isocalendar().week)
        == (year, week)
    ]
    return min(dates)


def _selection_events_for_exercise(
    exercise_name: str,
    workouts: list[WorkoutRecord],
    weeks: list[tuple[int, int]],
) -> list[ExerciseSelectionEvent]:
    """Introduced/disappeared/reappeared events across training weeks."""
    presence = _exercise_presence_by_week(exercise_name, workouts, weeks)
    events: list[ExerciseSelectionEvent] = []
    introduced = False
    active = False
    for year, week in weeks:
        occurrences = presence[(year, week)]
        if occurrences and not introduced:
            introduced, active = True, True
            events.append(
                ExerciseSelectionEvent(
                    exercise_name=exercise_name,
                    event_type="introduced",
                    week=_week_label(year, week),
                    date=min(occurrences).date().isoformat(),
                )
            )
        elif occurrences and not active:
            active = True
            events.append(
                ExerciseSelectionEvent(
                    exercise_name=exercise_name,
                    event_type="reappeared",
                    week=_week_label(year, week),
                    date=min(occurrences).date().isoformat(),
                )
            )
        elif not occurrences and active:
            active = False
            events.append(
                ExerciseSelectionEvent(
                    exercise_name=exercise_name,
                    event_type="disappeared",
                    week=_week_label(year, week),
                    date=_week_first_training_date(year, week, workouts),
                )
            )
    return events


def _build_frequencies(
    names: list[str], workouts: list[WorkoutRecord]
) -> list[ExerciseFrequency]:
    """Per-exercise frequency facts over total workouts as denominator."""
    total_workouts = len(workouts)
    frequencies: list[ExerciseFrequency] = []
    for name in names:
        occurrences = len(_exercise_workout_indexes(name, workouts))
        percent = (
            round(occurrences / total_workouts * 100, 2)
            if total_workouts
            else 0.0
        )
        frequencies.append(
            ExerciseFrequency(
                exercise_name=name,
                muscle=get_primary_muscle(name),
                workout_occurrences=occurrences,
                frequency_percent=percent,
                rarely_performed=percent <= RARELY_PERFORMED_MAX_PERCENT,
                frequently_performed=percent
                >= FREQUENTLY_PERFORMED_MIN_PERCENT,
            )
        )
    return frequencies


def _build_exercises_per_muscle(
    names: list[str],
) -> list[MuscleExerciseCount]:
    """Distinct mapped exercise counts grouped by primary muscle."""
    counts: dict[str, set[str]] = {}
    for name in names:
        muscle = get_primary_muscle(name)
        if muscle is None:
            continue  # unmapped: no artificial "Unknown" muscle
        counts.setdefault(muscle, set()).add(name)
    return [
        MuscleExerciseCount(muscle=muscle, exercise_count=len(counts[muscle]))
        for muscle in sorted(counts)
    ]


def _build_selection_events(
    names: list[str], workouts: list[WorkoutRecord]
) -> list[ExerciseSelectionEvent]:
    """All selection events, chronological by (date, exercise, event type)."""
    weeks = _training_weeks(workouts)
    events: list[ExerciseSelectionEvent] = []
    for name in names:
        events.extend(_selection_events_for_exercise(name, workouts, weeks))
    events.sort(key=lambda e: (e.date, e.exercise_name, e.event_type))
    return events


def _summarize_events(
    events: list[ExerciseSelectionEvent],
) -> SelectionSummary:
    """Count selection events by type."""
    return SelectionSummary(
        total_selection_events=len(events),
        introductions=sum(1 for e in events if e.event_type == "introduced"),
        disappearances=sum(1 for e in events if e.event_type == "disappeared"),
        reappearances=sum(1 for e in events if e.event_type == "reappeared"),
    )


def compute_exercise_variety(
    workouts: list[WorkoutRecord],
) -> ExerciseVarietyAnalysis:
    """Build exercise-variety facts from normalized workouts."""
    if not workouts:
        return ExerciseVarietyAnalysis()
    names = _distinct_exercise_names(workouts)
    events = _build_selection_events(names, workouts)
    return ExerciseVarietyAnalysis(
        total_workouts=len(workouts),
        distinct_exercises=len(names),
        exercises=names,
        frequencies=_build_frequencies(names, workouts),
        exercises_per_muscle=_build_exercises_per_muscle(names),
        selection_events=events,
        selection_summary=_summarize_events(events),
    )


def compute_single_exercise_variety(
    workouts: list[WorkoutRecord], exercise_name: str
) -> ExerciseVarietyAnalysis | None:
    """Variety facts filtered to one exercise (global denominator kept)."""
    if exercise_name not in _distinct_exercise_names(workouts):
        return None
    full = compute_exercise_variety(workouts)
    frequency = next(
        f for f in full.frequencies if f.exercise_name == exercise_name
    )
    muscle = frequency.muscle
    return ExerciseVarietyAnalysis(
        total_workouts=full.total_workouts,
        distinct_exercises=1,
        exercises=[exercise_name],
        frequencies=[frequency],
        exercises_per_muscle=(
            [MuscleExerciseCount(muscle=muscle, exercise_count=1)]
            if muscle is not None
            else []
        ),
        selection_events=[
            e for e in full.selection_events if e.exercise_name == exercise_name
        ],
        selection_summary=_summarize_events([
            e for e in full.selection_events if e.exercise_name == exercise_name
        ]),
    )


__all__ = [
    "RARELY_PERFORMED_MAX_PERCENT",
    "FREQUENTLY_PERFORMED_MIN_PERCENT",
    "ExerciseFrequency",
    "MuscleExerciseCount",
    "ExerciseSelectionEvent",
    "SelectionSummary",
    "ExerciseVarietyAnalysis",
    "compute_exercise_variety",
    "compute_single_exercise_variety",
]
