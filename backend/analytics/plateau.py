"""Plateau Detection (Phase 6).

Flags exercises whose heaviest-weight performance appears unchanged for at
least four consecutive ISO calendar weeks::

    List[WorkoutRecord]
            |
    compute_plateaus (deterministic, no I/O, no randomness, no LLM,
                      no pandas -- the normalized model is sufficient)
            |
    PlateauResponse (observed facts + the fixed label "Possible Plateau";
                     no interpretation, no recommendations)

Core rule: if an exercise's (heaviest weight, reps at that heaviest
weight) signature is identical across four consecutive performance weeks,
label it "Possible Plateau".

Definitions:
- Occurrence signature: heaviest valid weight in the workout/exercise;
  reps = maximum reps among sets AT that heaviest weight (not first,
  not average, not max reps at lighter weights).
- Weekly signature: across the week's occurrences, the highest heaviest
  weight; reps = highest reps at that weight. Multiple sessions in one
  week therefore cannot falsely break a plateau.
- Consecutive weeks: ISO (year, week) pairs whose Mondays are exactly
  7 days apart. A calendar week with no exercise performance breaks the
  sequence. Never inferred from 7-day spacing of observations.
- A run of >= 4 same-signature consecutive weeks becomes ONE plateau
  record (consecutive_weeks = run length), extended while the signature
  continues. A weight/reps change or a missing week ends the run.
- Validity reuses the Phase 4 rule (see analytics.prs.is_eligible_set):
  positive weight and positive integer reps, any set_type.
- plateau_start/end: observed performance dates in the boundary weeks
  (never invented). duration_days = (end - start) in days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from analytics.prs import is_eligible_set
from data.models import ExerciseRecord, WorkoutRecord

#: Minimum consecutive unchanged performance weeks to flag a plateau.
MIN_PLATEAU_WEEKS = 4

#: The only label plateau detection may emit (pattern, not proof).
PLATEAU_LABEL: Literal["Possible Plateau"] = "Possible Plateau"


@dataclass(frozen=True)
class _Occurrence:
    """One exercise occurrence reduced to its heaviest-weight signature."""

    start: datetime
    weight: float
    reps: int


@dataclass(frozen=True)
class _WeekSignature:
    """One ISO week's representative performance plus its observed date."""

    year: int
    week: int
    weight: float
    reps: int
    date: str  # YYYY-MM-DD of the determining occurrence


class PlateauWeekEvidence(BaseModel):
    """Structured evidence for one week of a plateau."""

    week: str = Field(description="ISO week label, e.g. '2026-W02'.")
    date: str = Field(description="Observed performance date (YYYY-MM-DD).")
    weight_kg: float
    reps: int


class ExercisePlateau(BaseModel):
    """One continuous plateau period for one exercise."""

    exercise_name: str
    label: Literal["Possible Plateau"] = PLATEAU_LABEL
    plateau_start: str = Field(description="Observed date in the first week.")
    plateau_end: str = Field(description="Observed date in the last week.")
    duration_days: int = Field(description="(plateau_end - plateau_start).days.")
    consecutive_weeks: int
    heaviest_weight_kg: float
    reps_at_heaviest_weight: int
    evidence: list[PlateauWeekEvidence] = Field(default_factory=list)


class PlateauResponse(BaseModel):
    """Detected plateaus, sorted by exercise name then plateau start."""

    plateaus: list[ExercisePlateau] = Field(default_factory=list)


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


def _summarize_occurrence(
    exercise: ExerciseRecord, start: datetime
) -> _Occurrence | None:
    """Reduce one occurrence to (heaviest weight, max reps at that weight)."""
    eligible: list[tuple[float, int]] = []
    for s in exercise.sets:
        if not is_eligible_set(s.weight_kg, s.reps):
            continue
        eligible.append(
            (float(s.weight_kg), int(s.reps))  # type: ignore[arg-type]
        )
    if not eligible:
        return None
    heaviest = max(w for w, _ in eligible)
    reps_at_heaviest = max(r for w, r in eligible if w == heaviest)
    return _Occurrence(start=start, weight=heaviest, reps=reps_at_heaviest)


def _weekly_signatures(
    occurrences: list[_Occurrence],
) -> list[_WeekSignature]:
    """Collapse occurrences into per-ISO-week best signatures, chronological."""
    by_week: dict[tuple[int, int], list[_Occurrence]] = {}
    for occ in occurrences:
        iso = occ.start.isocalendar()
        by_week.setdefault((iso.year, iso.week), []).append(occ)
    weeks: list[_WeekSignature] = []
    for (year, week) in sorted(by_week):
        occs = by_week[(year, week)]
        best_weight = max(o.weight for o in occs)
        at_best = [o for o in occs if o.weight == best_weight]
        best_reps = max(o.reps for o in at_best)
        # Earliest determining occurrence gives the representative date.
        chosen = min(
            (o for o in at_best if o.reps == best_reps),
            key=lambda o: o.start,
        )
        weeks.append(
            _WeekSignature(
                year=year,
                week=week,
                weight=best_weight,
                reps=best_reps,
                date=chosen.start.date().isoformat(),
            )
        )
    return weeks


def _week_monday(year: int, week: int) -> date:
    """Monday of an ISO (year, week); correct across year boundaries."""
    return date.fromisocalendar(year, week, 1)


def _exercise_occurrences(
    exercise_name: str, workouts: list[WorkoutRecord]
) -> list[_Occurrence]:
    """Chronological occurrence signatures for one exercise."""
    occurrences: list[_Occurrence] = []
    for workout in workouts:
        start = _parse_start(workout.start_time)
        if start is None:
            continue  # Phase 2 already drops these; never invent a date
        for exercise in workout.exercises:
            if exercise.exercise_name != exercise_name:
                continue
            occ = _summarize_occurrence(exercise, start)
            if occ is not None:
                occurrences.append(occ)
    occurrences.sort(key=lambda o: o.start)
    return occurrences


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


def _build_plateau(
    exercise_name: str, run: list[_WeekSignature]
) -> ExercisePlateau:
    """Build one plateau record from a run of same-signature consecutive weeks."""
    first, last = run[0], run[-1]
    start_date = date.fromisoformat(first.date)
    end_date = date.fromisoformat(last.date)
    return ExercisePlateau(
        exercise_name=exercise_name,
        plateau_start=first.date,
        plateau_end=last.date,
        duration_days=(end_date - start_date).days,
        consecutive_weeks=len(run),
        heaviest_weight_kg=round(first.weight, 2),
        reps_at_heaviest_weight=first.reps,
        evidence=[
            PlateauWeekEvidence(
                week=f"{w.year}-W{w.week:02d}",
                date=w.date,
                weight_kg=round(w.weight, 2),
                reps=w.reps,
            )
            for w in run
        ],
    )


def _detect_runs(weeks: list[_WeekSignature]) -> list[list[_WeekSignature]]:
    """Group weekly signatures into runs of same-signature consecutive weeks."""
    runs: list[list[_WeekSignature]] = []
    current: list[_WeekSignature] = []
    for week in weeks:
        continues = (
            current
            and (week.weight, week.reps)
            == (current[-1].weight, current[-1].reps)
            and (
                _week_monday(week.year, week.week)
                - _week_monday(current[-1].year, current[-1].week)
            ).days
            == 7
        )
        if continues:
            current.append(week)
        else:
            if current:
                runs.append(current)
            current = [week]
    if current:
        runs.append(current)
    return runs


def _exercise_plateaus(
    exercise_name: str, workouts: list[WorkoutRecord]
) -> list[ExercisePlateau]:
    """All plateau periods (>= 4 weeks) for one exercise."""
    weeks = _weekly_signatures(_exercise_occurrences(exercise_name, workouts))
    return [
        _build_plateau(exercise_name, run)
        for run in _detect_runs(weeks)
        if len(run) >= MIN_PLATEAU_WEEKS
    ]


def compute_plateaus(
    workouts: list[WorkoutRecord],
) -> PlateauResponse:
    """Detect plateau periods across all normalized exercises."""
    plateaus: list[ExercisePlateau] = []
    for name in _all_exercise_names(workouts):
        plateaus.extend(_exercise_plateaus(name, workouts))
    plateaus.sort(key=lambda p: (p.exercise_name, p.plateau_start))
    return PlateauResponse(plateaus=plateaus)


def compute_exercise_plateaus(
    workouts: list[WorkoutRecord], exercise_name: str
) -> list[ExercisePlateau]:
    """Plateau periods for a single exercise ([], never 404-worthy here)."""
    return _exercise_plateaus(exercise_name, workouts)


__all__ = [
    "MIN_PLATEAU_WEEKS",
    "PLATEAU_LABEL",
    "PlateauWeekEvidence",
    "ExercisePlateau",
    "PlateauResponse",
    "compute_plateaus",
    "compute_exercise_plateaus",
]
