"""PR Engine (Phase 4).

Consumes the Phase 2 normalized workout model::

    List[WorkoutRecord]
            |
    generate_exercise_prs (deterministic, no I/O, no randomness, no LLM)
            |
    List[ExercisePR] (structured facts -- no judgments or recommendations)

Eligibility rule (V1):
    Any set with valid positive weight and positive integer reps is eligible,
    REGARDLESS of set_type. Missing/invalid/zero/negative values are never
    converted to zero or inferred -- such sets are simply ineligible.
    Rationale: set_type describes intent (warm-up, dropset, ...), not
    performance; a heavy dropset/failure set is legitimate performance data.

Per-exercise PRs (Epley formula throughout):
    weight_pr        = max eligible weight_kg                    (kg, 2 dp)
    rep_pr           = max eligible reps                         (int reps)
    volume_pr        = max(weight_kg * reps) over eligible sets  (kg, 2 dp)
    estimated_1rm_pr = max(weight * (1 + reps / 30))             (kg, 2 dp)

Ties resolve to the earliest occurrence: candidates are scanned in
workout-start order and strict `>` comparison keeps the first maximum.
PR dates are the workout start date (YYYY-MM-DD) of the winning set;
unparseable dates become None (never fabricated).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

from data.models import WorkoutRecord


@dataclass(frozen=True)
class _Candidate:
    """One PR-eligible set with its workout context."""

    date: str | None
    start_key: str
    weight: float
    reps: int


class WeightPR(BaseModel):
    value: float = Field(description="Heaviest eligible weight in kg.")
    unit: str = "kg"
    date: str | None = Field(
        default=None, description="Workout start date (YYYY-MM-DD) of the PR set."
    )


class RepPR(BaseModel):
    value: int = Field(description="Highest eligible rep count.")
    unit: str = "reps"
    date: str | None = None


class VolumePR(BaseModel):
    value: float = Field(description="Highest single-set weight x reps in kg.")
    unit: str = "kg"
    weight: float = Field(description="Weight (kg) of the PR set.")
    reps: int = Field(description="Reps of the PR set.")
    date: str | None = None


class Estimated1RMPR(BaseModel):
    value: float = Field(description="Highest Epley estimated 1RM in kg.")
    unit: str = "kg"
    weight: float = Field(description="Weight (kg) of the PR set.")
    reps: int = Field(description="Reps of the PR set.")
    date: str | None = None


class ExercisePR(BaseModel):
    """Structured PR facts for one distinct normalized exercise."""

    exercise_name: str
    weight_pr: WeightPR | None = None
    rep_pr: RepPR | None = None
    volume_pr: VolumePR | None = None
    estimated_1rm_pr: Estimated1RMPR | None = None


def calculate_estimated_1rm(weight_kg: float, reps: int) -> float:
    """Epley formula: weight x (1 + reps / 30), rounded to 2 decimals."""
    return round(weight_kg * (1 + reps / 30), 2)


def _is_eligible(weight: object, reps: object) -> bool:
    """Eligibility: positive weight and positive integer reps (any set_type)."""
    if isinstance(weight, bool) or isinstance(reps, bool):
        return False
    if not isinstance(weight, (int, float)) or not isinstance(reps, (int, float)):
        return False
    if not weight > 0:
        return False
    if isinstance(reps, float) and not reps.is_integer():
        return False
    return reps > 0


def _workout_date(start_time: str | None) -> tuple[str | None, str]:
    """Return (YYYY-MM-DD date or None, sortable key) for a workout start.

    The date is derived from the normalized ISO start_time; unparseable
    values yield None (never fabricated).
    """
    if not start_time or not isinstance(start_time, str):
        return None, ""
    try:
        date = datetime.fromisoformat(start_time).date().isoformat()
    except ValueError:
        return None, start_time
    return date, start_time


def _collect_candidates(
    workouts: list[WorkoutRecord],
) -> dict[str, list[_Candidate]]:
    """Group eligible sets per exercise, in deterministic workout-start order."""
    ordered = sorted(workouts, key=lambda w: w.start_time or "")
    candidates: dict[str, list[_Candidate]] = {}
    for workout in ordered:
        date, key = _workout_date(workout.start_time)
        for exercise in workout.exercises:
            name = exercise.exercise_name
            if not name or not name.strip():
                continue
            for s in exercise.sets:
                if not _is_eligible(s.weight_kg, s.reps):
                    continue
                weight = float(s.weight_kg)  # type: ignore[arg-type]
                reps = int(s.reps)  # type: ignore[arg-type]
                candidates.setdefault(name, []).append(
                    _Candidate(date=date, start_key=key, weight=weight, reps=reps)
                )
    return candidates


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


def calculate_weight_pr(candidates: list[_Candidate]) -> WeightPR | None:
    """Maximum eligible weight (earliest occurrence wins ties)."""
    best: _Candidate | None = None
    for c in candidates:
        if best is None or c.weight > best.weight:
            best = c
    if best is None:
        return None
    return WeightPR(value=round(best.weight, 2), date=best.date)


def calculate_rep_pr(candidates: list[_Candidate]) -> RepPR | None:
    """Maximum eligible reps (earliest occurrence wins ties)."""
    best: _Candidate | None = None
    for c in candidates:
        if best is None or c.reps > best.reps:
            best = c
    if best is None:
        return None
    return RepPR(value=best.reps, date=best.date)


def calculate_volume_pr(candidates: list[_Candidate]) -> VolumePR | None:
    """Maximum single-set weight x reps (earliest occurrence wins ties)."""
    best: _Candidate | None = None
    best_volume = 0.0
    for c in candidates:
        volume = c.weight * c.reps
        if best is None or volume > best_volume:
            best, best_volume = c, volume
    if best is None:
        return None
    return VolumePR(
        value=round(best_volume, 2),
        weight=round(best.weight, 2),
        reps=best.reps,
        date=best.date,
    )


def calculate_estimated_1rm_pr(
    candidates: list[_Candidate],
) -> Estimated1RMPR | None:
    """Maximum Epley estimated 1RM (earliest occurrence wins ties)."""
    best: _Candidate | None = None
    best_epley = 0.0
    for c in candidates:
        epley = c.weight * (1 + c.reps / 30)
        if best is None or epley > best_epley:
            best, best_epley = c, epley
    if best is None:
        return None
    return Estimated1RMPR(
        value=round(best_epley, 2),
        weight=round(best.weight, 2),
        reps=best.reps,
        date=best.date,
    )


def generate_exercise_prs(workouts: list[WorkoutRecord]) -> list[ExercisePR]:
    """Build per-exercise PR facts for the whole normalized dataset.

    Every distinct exercise is listed; exercises without eligible sets get
    null PR fields rather than being omitted.
    """
    candidates = _collect_candidates(workouts)
    return [
        ExercisePR(
            exercise_name=name,
            weight_pr=calculate_weight_pr(candidates.get(name, [])),
            rep_pr=calculate_rep_pr(candidates.get(name, [])),
            volume_pr=calculate_volume_pr(candidates.get(name, [])),
            estimated_1rm_pr=calculate_estimated_1rm_pr(
                candidates.get(name, [])
            ),
        )
        for name in _all_exercise_names(workouts)
    ]
