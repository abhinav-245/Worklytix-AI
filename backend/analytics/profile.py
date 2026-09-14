"""User Profile & Bodyweight Analysis (Phase 9).

In-memory V1 profile layer (no database, no auth, no persistence)::

    User Input (POST /profile)
            |
    Pydantic validation (422 on invalid input, never silently corrected)
            |
    Deterministic calculations (no LLM, no recommendations)
            |
    ProfileAnalysis (profile context + training-history facts)

Provided calculations:
- Training history: earliest/latest normalized workout calendar dates,
  duration in days, human-readable calendar duration, and the observed
  training-history level (Beginner < 1 year <= Intermediate < 3 years
  <= Advanced). The level describes OBSERVED DATA DURATION ONLY, never
  athletic ability or strength.
- Bodyweight ratios: weight_pr / body_weight_kg and
  estimated_1rm_pr / body_weight_kg (2 dp), attached to existing PR
  records without altering the underlying PR values. Missing PR values
  stay null; a missing body weight means no ratios.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from analytics.prs import ExercisePR
from data.models import WorkoutRecord

#: Maximum accepted age (upper validation boundary).
MAX_AGE = 120

#: Maximum accepted body weight in kg (guards against obvious typos).
MAX_BODY_WEIGHT_KG = 1000.0

#: Full calendar years below which observed history is Beginner.
INTERMEDIATE_MIN_YEARS = 1

#: Full calendar years at or above which observed history is Advanced.
ADVANCED_MIN_YEARS = 3

FitnessGoal = Literal["muscle_gain", "strength", "fat_loss", "general_fitness"]

#: Human-readable goal labels (frontend display mapping).
GOAL_LABELS: dict[str, str] = {
    "muscle_gain": "Muscle Gain",
    "strength": "Strength",
    "fat_loss": "Fat Loss",
    "general_fitness": "General Fitness",
}

TrainingHistoryLevel = Literal["Beginner", "Intermediate", "Advanced"]


class UserProfile(BaseModel):
    """Validated V1 user profile (in-memory only)."""

    age: int = Field(
        gt=0,
        le=MAX_AGE,
        description="Age in years (integer, 1-120).",
    )
    body_weight_kg: float = Field(
        gt=0,
        le=MAX_BODY_WEIGHT_KG,
        description="Body weight in kilograms (stored unrounded).",
    )
    goal: FitnessGoal = Field(
        description="Profile context only; drives no recommendations."
    )


class TrainingHistory(BaseModel):
    """Observed training-history facts from normalized workout dates."""

    start_date: str = Field(description="Earliest workout date (YYYY-MM-DD).")
    end_date: str = Field(description="Latest workout date (YYYY-MM-DD).")
    duration_days: int = Field(
        description="Calendar-date difference (never negative)."
    )
    duration_text: str = Field(
        description="Deterministic human-readable calendar duration."
    )
    level: TrainingHistoryLevel = Field(
        description="Observed data-duration level, NOT athletic ability."
    )


class ProfileAnalysis(BaseModel):
    """Profile context plus derived training-history facts."""

    profile: UserProfile
    training_history: TrainingHistory | None = Field(
        default=None,
        description="None when no workouts have been uploaded yet.",
    )


def _parse_start(start_time: str | None) -> datetime | None:
    """Parse a normalized ISO start_time; unparseable -> None (never guessed)."""
    if not start_time or not isinstance(start_time, str):
        return None
    try:
        return datetime.fromisoformat(start_time)
    except ValueError:
        return None


def _full_calendar_years(start: date, end: date) -> int:
    """Complete calendar years elapsed from start to end (end >= start)."""
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


def _duration_text(start: date, end: date) -> str:
    """Deterministic calendar duration, e.g. '2 years, 3 months, 19 days'."""
    years = _full_calendar_years(start, end)
    anchor_year = start.year + years
    anchor_month = start.month
    anchor_day = min(start.day, _days_in_month(anchor_year, start.month))
    anchor = date(anchor_year, anchor_month, anchor_day)
    months = (end.year - anchor.year) * 12 + (end.month - anchor.month)
    if end.day < anchor.day:
        months -= 1
    cursor_year = anchor.year + (anchor.month - 1 + months) // 12
    cursor_month = (anchor.month - 1 + months) % 12 + 1
    cursor_day = min(anchor.day, _days_in_month(cursor_year, cursor_month))
    cursor = date(cursor_year, cursor_month, cursor_day)
    days = (end - cursor).days
    parts: list[str] = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days or not parts:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    return ", ".join(parts)


def _days_in_month(year: int, month: int) -> int:
    """Days in a calendar month (leap-year aware)."""
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def classify_training_history_level(start: date, end: date) -> TrainingHistoryLevel:
    """Classify OBSERVED data duration (never ability or strength)."""
    years = _full_calendar_years(start, end)
    if years >= ADVANCED_MIN_YEARS:
        return "Advanced"
    if years >= INTERMEDIATE_MIN_YEARS:
        return "Intermediate"
    return "Beginner"


def compute_training_history(
    workouts: list[WorkoutRecord],
) -> TrainingHistory | None:
    """Training-history facts from normalized dates; None when unavailable."""
    starts = [
        s for s in (_parse_start(w.start_time) for w in workouts) if s is not None
    ]
    if not starts:
        return None
    first = min(starts).date()
    last = max(starts).date()
    return TrainingHistory(
        start_date=first.isoformat(),
        end_date=last.isoformat(),
        duration_days=(last - first).days,
        duration_text=_duration_text(first, last),
        level=classify_training_history_level(first, last),
    )


def calculate_bodyweight_ratio(load_kg: float, body_weight_kg: float) -> float:
    """Load-to-bodyweight ratio (load / body weight), rounded to 2 decimals."""
    return round(load_kg / body_weight_kg, 2)


def attach_bodyweight_ratios(
    prs: list[ExercisePR], body_weight_kg: float
) -> list[ExercisePR]:
    """Return PR copies with bodyweight ratios filled in.

    Original PR values are never modified; exercises without a valid
    weight/1RM PR keep null ratios.
    """
    enriched: list[ExercisePR] = []
    for pr in prs:
        update: dict[str, float | None] = {}
        if pr.weight_pr is not None:
            update["weight_pr_ratio"] = calculate_bodyweight_ratio(
                pr.weight_pr.value, body_weight_kg
            )
        if pr.estimated_1rm_pr is not None:
            update["estimated_1rm_pr_ratio"] = calculate_bodyweight_ratio(
                pr.estimated_1rm_pr.value, body_weight_kg
            )
        enriched.append(pr.model_copy(update=update))
    return enriched


__all__ = [
    "MAX_AGE",
    "MAX_BODY_WEIGHT_KG",
    "INTERMEDIATE_MIN_YEARS",
    "ADVANCED_MIN_YEARS",
    "FitnessGoal",
    "GOAL_LABELS",
    "TrainingHistoryLevel",
    "UserProfile",
    "TrainingHistory",
    "ProfileAnalysis",
    "classify_training_history_level",
    "compute_training_history",
    "calculate_bodyweight_ratio",
    "attach_bodyweight_ratios",
]
