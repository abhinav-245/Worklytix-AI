"""Structured AI context builder (Phase 12).

Builds a compact, versioned analytics context from the deterministic
engines (overview, PRs, progression, volume, plateaus, muscles, exercise
variety, profile). Never reads the raw CSV. Summaries are always included;
per-point detail only for the deterministically detected focus exercise
(or none), keeping prompts compact on large datasets.

Every meaningful fact gets a stable, collision-safe ID
(``category:subject:metric[:extra]``) registered in a backend-side
grounding index used to validate Gemini's observations. IDs are never
random and Gemini cannot create facts. Each ID is ALSO embedded in the
context payload itself (``{"value": ..., "fact_id": ...}``), because
Gemini may only cite IDs it was actually supplied -- it must copy them
exactly, never construct them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from analytics.exercise_variety import compute_exercise_variety
from analytics.muscles import compute_muscles
from analytics.overview import compute_overview
from analytics.plateau import compute_plateaus
from analytics.profile import (
    UserProfile,
    attach_bodyweight_ratios,
    compute_training_history,
)
from analytics.progression import compute_progression
from analytics.prs import generate_exercise_prs
from analytics.volume import compute_volume
from data.models import WorkoutRecord

CONTEXT_VERSION = "v1"
MAX_SELECTION_EVENTS = 100


class AIContext(BaseModel):
    """Versioned analytics payload serialized into the Gemini prompt."""

    context_version: str = CONTEXT_VERSION
    profile: dict = Field(default_factory=dict)
    overview: dict = Field(default_factory=dict)
    prs: list[dict] = Field(default_factory=list)
    progression_summary: list[dict] = Field(default_factory=list)
    progression_detail: dict[str, list[dict]] = Field(default_factory=dict)
    volume_summary: list[dict] = Field(default_factory=list)
    volume_detail: dict[str, list[dict]] = Field(default_factory=dict)
    plateaus: list[dict] = Field(default_factory=list)
    muscles: list[dict] = Field(default_factory=list)
    exercise_variety: dict = Field(default_factory=dict)
    exercise_variety_detail: dict = Field(default_factory=dict)


@dataclass
class Fact:
    """One backend-registered grounding fact."""

    id: str
    category: str
    subject: str
    metric: str
    value: object = None
    unit: str | None = None
    date: str | None = None


@dataclass
class GroundingIndex:
    """Backend-side validation registry (never sent to Gemini)."""

    facts: dict[str, Fact] = field(default_factory=dict)
    allowed_numbers: set[float] = field(default_factory=set)
    allowed_dates: set[str] = field(default_factory=set)
    allowed_weeks: set[str] = field(default_factory=set)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def slugify(name: str) -> str:
    """Deterministic slug: lowercase, non-alnum runs become one underscore."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _register(
    index: GroundingIndex,
    fact_id: str,
    category: str,
    subject: str,
    metric: str,
    value: object,
    unit: str | None = None,
    date: str | None = None,
) -> None:
    """Register a fact and harvest its scalar for value validation."""
    index.facts[fact_id] = Fact(
        id=fact_id, category=category, subject=subject,
        metric=metric, value=value, unit=unit, date=date,
    )
    if date is not None and _DATE_RE.match(date):
        index.allowed_dates.add(date)
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        index.allowed_numbers.add(float(value))
    elif isinstance(value, str):
        if _DATE_RE.match(value):
            index.allowed_dates.add(value)
        elif _WEEK_RE.match(value):
            index.allowed_weeks.add(value)


def _cite(value: object, fact_id: str, unit: str | None = None) -> dict:
    """Wrap a registered context value with the exact fact ID to cite.

    Gemini must copy ``fact_id`` verbatim into observation ``fact_ids``;
    validation requires an exact registered-ID match (no fuzzy matching).
    """
    cited: dict[str, object] = {"value": value, "fact_id": fact_id}
    if unit is not None:
        cited["unit"] = unit
    return cited


def _base_title(name: str) -> str:
    """Title without parenthetical variant, e.g. 'Bench Press'."""
    return name.split(" (")[0].strip()


def detect_focus_exercises(
    question: str, exercise_names: list[str]
) -> list[str]:
    """Deterministic exercise match: full or base title as question substring.

    Case-insensitive substring match against normalized titles only -- no
    fuzzy matching, no invented names. All matching titles are returned
    (e.g. "Bench Press" matches both barbell and dumbbell variants);
    empty list when nothing matches.
    """
    lowered = question.lower()
    matched = [
        name
        for name in exercise_names
        if name.lower() in lowered or _base_title(name).lower() in lowered
    ]
    return sorted(set(matched))


def detect_focus_exercise(
    question: str, exercise_names: list[str]
) -> str | None:
    """Single most-specific match, or None (legacy helper)."""
    matched = detect_focus_exercises(question, exercise_names)
    if not matched:
        return None
    return sorted(matched, key=len, reverse=True)[0]


def _pr_dict(pr: object) -> dict:
    """Serialize one ExercisePR to plain data (None fields preserved)."""
    return {
        "exercise_name": pr.exercise_name,  # type: ignore[attr-defined]
        "weight_pr": (
            pr.weight_pr.model_dump()  # type: ignore[attr-defined]
            if pr.weight_pr is not None  # type: ignore[attr-defined]
            else None
        ),
        "rep_pr": (
            pr.rep_pr.model_dump()  # type: ignore[attr-defined]
            if pr.rep_pr is not None  # type: ignore[attr-defined]
            else None
        ),
        "volume_pr": (
            pr.volume_pr.model_dump()  # type: ignore[attr-defined]
            if pr.volume_pr is not None  # type: ignore[attr-defined]
            else None
        ),
        "estimated_1rm_pr": (
            pr.estimated_1rm_pr.model_dump()  # type: ignore[attr-defined]
            if pr.estimated_1rm_pr is not None  # type: ignore[attr-defined]
            else None
        ),
        "weight_pr_ratio": pr.weight_pr_ratio,  # type: ignore[attr-defined]
        "estimated_1rm_pr_ratio": (
            pr.estimated_1rm_pr_ratio  # type: ignore[attr-defined]
        ),
    }


def build_ai_context(
    workouts: list[WorkoutRecord],
    profile: UserProfile | None,
    focus_exercises: list[str] | None = None,
) -> tuple[AIContext, GroundingIndex]:
    """Build the versioned context plus the backend grounding index."""
    index = GroundingIndex()

    overview = compute_overview(workouts)
    overview_dict = overview.model_dump()
    for metric, value in overview_dict.items():
        if value is not None:
            fact_id = f"overview:dataset:{metric}"
            _register(
                index, fact_id, "overview",
                "dataset", metric, value,
            )
            overview_dict[metric] = _cite(value, fact_id)

    profile_dict: dict = {}
    if profile is not None:
        history = compute_training_history(workouts)
        history_dict = (
            history.model_dump() if history is not None else None
        )
        if history_dict is not None:
            for hist_metric, hist_unit in (
                ("duration_days", "days"),
                ("level", None),
                ("start_date", None),
                ("end_date", None),
            ):
                hist_fact_id = f"profile:{hist_metric}"
                history_dict[hist_metric] = _cite(
                    history_dict[hist_metric], hist_fact_id,
                    unit=hist_unit,
                )
            # The human-readable duration text itself is citable prose
            # (e.g. "2 years, 3 months, 19 days"); register it so the
            # model can reference the duration statement exactly.
            history_dict["duration_text"] = _cite(
                history_dict["duration_text"], "profile:duration_text",
            )
            # Calendar components parsed from duration_text (e.g. the 2
            # and 3 in "2 years, 3 months, 19 days") are registered facts;
            # expose the year/month components alongside the history so
            # Gemini can cite them exactly.
            for amount, unit_word in re.findall(
                r"(\d+)\s*(year|month)s?", history.duration_text
            ):
                part_fact_id = f"profile:duration_{unit_word}s"
                history_dict[f"duration_{unit_word}s"] = _cite(
                    int(amount), part_fact_id, unit=f"{unit_word}s",
                )
        profile_dict = {
            "age": _cite(profile.age, "profile:age"),
            "body_weight_kg": _cite(
                profile.body_weight_kg, "profile:body_weight_kg",
                unit="kg",
            ),
            "goal": _cite(profile.goal, "profile:goal"),
            "training_history": history_dict,
        }
        _register(index, "profile:age", "profile", "user", "age", profile.age)
        _register(
            index, "profile:body_weight_kg", "profile", "user",
            "body_weight_kg", profile.body_weight_kg, unit="kg",
        )
        _register(
            index, "profile:goal", "profile", "user", "goal", profile.goal
        )
        if history is not None:
            _register(
                index, "profile:duration_days", "profile", "user",
                "duration_days", history.duration_days, unit="days",
            )
            _register(
                index, "profile:level", "profile", "user", "level",
                history.level,
            )
            _register(
                index, "profile:start_date", "profile", "user", "start_date",
                history.start_date,
            )
            _register(
                index, "profile:end_date", "profile", "user", "end_date",
                history.end_date,
            )
            _register(
                index, "profile:duration_text", "profile", "user",
                "duration_text", history.duration_text,
            )
            # Calendar components of the human-readable duration (e.g. the
            # 2, 3 and 19 in "2 years, 3 months, 19 days") so grounded
            # duration prose validates.
            for amount, unit_word in re.findall(
                r"(\d+)\s*(year|month|day)s?", history.duration_text
            ):
                _register(
                    index, f"profile:duration_{unit_word}s", "profile",
                    "user", f"duration_{unit_word}s", int(amount),
                    unit=f"{unit_word}s",
                )

    prs = generate_exercise_prs(workouts)
    if profile is not None:
        prs = attach_bodyweight_ratios(prs, profile.body_weight_kg)
    pr_dicts: list[dict] = []
    for pr in prs:
        entry = _pr_dict(pr)
        pr_dicts.append(entry)
        slug = slugify(pr.exercise_name)
        for metric in (
            "weight_pr", "rep_pr", "volume_pr", "estimated_1rm_pr",
        ):
            item = entry[metric]
            if item is not None:
                fact_id = f"pr:{slug}:{metric}"
                _register(
                    index, fact_id, "pr", pr.exercise_name,
                    metric, item["value"], unit=item.get("unit"),
                    date=item.get("date"),
                )
                item["fact_id"] = fact_id
        for metric in ("weight_pr_ratio", "estimated_1rm_pr_ratio"):
            if entry[metric] is not None:
                fact_id = f"pr:{slug}:{metric}"
                _register(
                    index, fact_id, "pr", pr.exercise_name,
                    metric, entry[metric],
                )
                entry[metric] = _cite(entry[metric], fact_id)

    progression = compute_progression(workouts)
    prog_summaries: list[dict] = []
    for ex in progression.exercises:
        hist = ex.history
        if hist:
            first, last = hist[0], hist[-1]
            summary = {
                "exercise_name": ex.exercise_name,
                "n_observations": len(hist),
                "first_date": first.date,
                "last_date": last.date,
                "first_weight_kg": first.weight_kg,
                "last_weight_kg": last.weight_kg,
                "max_weight_kg": max(p.weight_kg for p in hist),
                "max_reps": max(p.reps for p in hist),
                "max_volume_kg": max(p.volume_kg for p in hist),
                "max_estimated_1rm_kg": max(p.estimated_1rm_kg for p in hist),
            }
        else:
            summary = {
                "exercise_name": ex.exercise_name,
                "n_observations": 0,
            }
        prog_summaries.append(summary)
        slug = slugify(ex.exercise_name)
        n_obs_id = f"progression:{slug}:n_observations"
        _register(
            index, n_obs_id, "progression",
            ex.exercise_name, "n_observations", summary["n_observations"],
        )
        summary["n_observations"] = _cite(
            summary["n_observations"], n_obs_id
        )
        for metric in (
            "first_date", "last_date", "first_weight_kg", "last_weight_kg",
            "max_weight_kg", "max_reps", "max_volume_kg",
            "max_estimated_1rm_kg",
        ):
            if metric in summary:
                fact_id = f"progression:{slug}:{metric}"
                _register(
                    index, fact_id, "progression",
                    ex.exercise_name, metric, summary[metric],
                )
                summary[metric] = _cite(summary[metric], fact_id)

    prog_detail: dict[str, list[dict]] = {}
    for focus_exercise in focus_exercises or []:
        match = next(
            (e for e in progression.exercises
             if e.exercise_name == focus_exercise),
            None,
        )
        if match is not None:
            points = [p.model_dump() for p in match.history]
            prog_detail[focus_exercise] = points
            slug = slugify(focus_exercise)
            for p in points:
                for metric in (
                    "weight_kg", "reps", "volume_kg", "estimated_1rm_kg",
                ):
                    fact_id = (
                        f"progression:{slug}:{p['date']}:{metric}"
                    )
                    _register(
                        index,
                        fact_id,
                        "progression", focus_exercise, metric,
                        p[metric], date=p["date"],
                    )
                    p[metric] = _cite(p[metric], fact_id)

    volume = compute_volume(workouts)
    vol_summaries: list[dict] = []
    for ex in volume.exercises:
        hist = ex.history
        total = round(sum(p.volume_kg for p in hist), 2)
        summary = {
            "exercise_name": ex.exercise_name,
            "n_observations": len(hist),
            "total_volume_kg": total,
            "first_date": hist[0].date if hist else None,
            "last_date": hist[-1].date if hist else None,
        }
        vol_summaries.append(summary)
        slug = slugify(ex.exercise_name)
        total_id = f"volume:{slug}:total_volume_kg"
        _register(
            index, total_id, "volume",
            ex.exercise_name, "total_volume_kg", total, unit="kg",
        )
        summary["total_volume_kg"] = _cite(total, total_id, unit="kg")
        vol_n_obs_id = f"volume:{slug}:n_observations"
        _register(
            index, vol_n_obs_id, "volume",
            ex.exercise_name, "n_observations", len(hist),
        )
        summary["n_observations"] = _cite(
            summary["n_observations"], vol_n_obs_id
        )

    vol_detail: dict[str, list[dict]] = {}
    for focus_exercise in focus_exercises or []:
        match = next(
            (e for e in volume.exercises
             if e.exercise_name == focus_exercise),
            None,
        )
        if match is not None:
            points = [p.model_dump() for p in match.history]
            vol_detail[focus_exercise] = points
            slug = slugify(focus_exercise)
            for p in points:
                vol_fact_id = (
                    f"volume:{slug}:{p['date']}:volume_kg"
                )
                _register(
                    index, vol_fact_id,
                    "volume", focus_exercise, "volume_kg",
                    p["volume_kg"], unit="kg", date=p["date"],
                )
                p["volume_kg"] = _cite(
                    p["volume_kg"], vol_fact_id, unit="kg"
                )

    plateaus = compute_plateaus(workouts)
    plateau_dicts: list[dict] = []
    for i, pl in enumerate(plateaus.plateaus):
        entry = pl.model_dump()
        plateau_dicts.append(entry)
        slug = slugify(pl.exercise_name)
        base = f"plateau:{slug}:{pl.plateau_start}-to-{pl.plateau_end}"
        for plat_metric, plat_unit in (
            ("heaviest_weight_kg", "kg"),
            ("reps_at_heaviest_weight", "reps"),
            ("consecutive_weeks", "weeks"),
            ("duration_days", "days"),
            ("plateau_start", None),
            ("plateau_end", None),
        ):
            plat_fact_id = f"{base}:{plat_metric}"
            _register(index, plat_fact_id, "plateau",
                      pl.exercise_name, plat_metric,
                      entry[plat_metric], unit=plat_unit)
            entry[plat_metric] = _cite(
                entry[plat_metric], plat_fact_id, unit=plat_unit
            )
        for ev_entry, ev in zip(entry["evidence"], pl.evidence):
            ev_id = f"{base}:{ev.week}:weight_kg"
            _register(index, ev_id, "plateau", pl.exercise_name,
                      "evidence_weight_kg", ev.weight_kg, unit="kg",
                      date=ev.date)
            ev_entry["weight_kg"] = _cite(
                ev_entry["weight_kg"], ev_id, unit="kg"
            )
            ev_reps_id = f"{base}:{ev.week}:reps"
            _register(index, ev_reps_id, "plateau",
                      pl.exercise_name, "evidence_reps", ev.reps,
                      unit="reps", date=ev.date)
            ev_entry["reps"] = _cite(
                ev_entry["reps"], ev_reps_id, unit="reps"
            )
            index.allowed_weeks.add(ev.week)
        _ = i

    muscles = compute_muscles(workouts)
    muscle_dicts: list[dict] = []
    for m in muscles.muscles:
        entry = m.model_dump()
        muscle_dicts.append(entry)
        slug = slugify(m.muscle)
        for mus_metric, mus_unit in (
            ("total_sets", "sets"),
            ("training_sessions", "workouts"),
            ("exercise_variety", "exercises"),
        ):
            mus_fact_id = f"muscle:{slug}:{mus_metric}"
            _register(index, mus_fact_id, "muscle",
                      m.muscle, mus_metric, entry[mus_metric],
                      unit=mus_unit)
            entry[mus_metric] = _cite(
                entry[mus_metric], mus_fact_id, unit=mus_unit
            )
        if m.average_sessions_per_week is not None:
            avg_fact_id = f"muscle:{slug}:average_sessions_per_week"
            _register(index, avg_fact_id,
                      "muscle", m.muscle, "average_sessions_per_week",
                      m.average_sessions_per_week)
            entry["average_sessions_per_week"] = _cite(
                entry["average_sessions_per_week"], avg_fact_id
            )
        # The neglected flag is a deterministic boolean fact; register it
        # so "potentially neglected" statements can cite it exactly.
        neg_fact_id = f"muscle:{slug}:potentially_neglected"
        _register(index, neg_fact_id, "muscle",
                  m.muscle, "potentially_neglected",
                  m.potentially_neglected)
        entry["potentially_neglected"] = _cite(
            entry["potentially_neglected"], neg_fact_id
        )
    mapping = muscles.mapping.model_dump()
    for metric in (
        "total_exercises", "mapped_exercises", "unmapped_exercises",
        "coverage_percent",
    ):
        _register(index, f"muscle:mapping:{metric}", "muscle",
                  "mapping", metric, mapping[metric])

    variety = compute_exercise_variety(workouts)
    var_total_id = "variety:dataset:total_workouts"
    variety_dict = {
        "total_workouts": _cite(
            variety.total_workouts, var_total_id, unit="workouts"
        ),
        "distinct_exercises": _cite(
            variety.distinct_exercises,
            "variety:dataset:distinct_exercises",
            unit="exercises",
        ),
        "frequencies": [],
        "exercises_per_muscle": [],
        "selection_summary": {},
    }
    _register(index, var_total_id, "variety",
              "dataset", "total_workouts", variety.total_workouts,
              unit="workouts")
    _register(index, "variety:dataset:distinct_exercises", "variety",
              "dataset", "distinct_exercises", variety.distinct_exercises,
              unit="exercises")
    for f in variety.frequencies:
        freq_entry = f.model_dump()
        slug = slugify(f.exercise_name)
        occ_fact_id = f"variety:{slug}:workout_occurrences"
        _register(index, occ_fact_id, "variety",
                  f.exercise_name, "workout_occurrences",
                  f.workout_occurrences, unit="workouts")
        freq_entry["workout_occurrences"] = _cite(
            freq_entry["workout_occurrences"], occ_fact_id,
            unit="workouts",
        )
        pct_fact_id = f"variety:{slug}:frequency_percent"
        _register(index, pct_fact_id, "variety",
                  f.exercise_name, "frequency_percent",
                  f.frequency_percent, unit="percent")
        freq_entry["frequency_percent"] = _cite(
            freq_entry["frequency_percent"], pct_fact_id,
            unit="percent",
        )
        variety_dict["frequencies"].append(freq_entry)
    for m in variety.exercises_per_muscle:
        epm_entry = m.model_dump()
        epm_fact_id = (
            f"variety:muscle:{slugify(m.muscle)}:exercise_count"
        )
        _register(index, epm_fact_id,
                  "variety", m.muscle, "exercise_count", m.exercise_count,
                  unit="exercises")
        epm_entry["exercise_count"] = _cite(
            epm_entry["exercise_count"], epm_fact_id, unit="exercises"
        )
        variety_dict["exercises_per_muscle"].append(epm_entry)
    for metric, value in variety.selection_summary.model_dump().items():
        sel_fact_id = f"variety:selection:{metric}"
        _register(index, sel_fact_id, "variety",
                  "selection", metric, value)
        variety_dict["selection_summary"][metric] = _cite(
            value, sel_fact_id
        )
    mapping = muscles.mapping.model_dump()
    variety_dict["mapping"] = {}
    for metric in (
        "total_exercises", "mapped_exercises", "unmapped_exercises",
        "coverage_percent",
    ):
        map_fact_id = f"muscle:mapping:{metric}"
        variety_dict["mapping"][metric] = _cite(
            mapping[metric], map_fact_id
        )
    recent_events = sorted(
        variety.selection_events,
        key=lambda e: (e.date, e.exercise_name, e.event_type),
        reverse=True,
    )[:MAX_SELECTION_EVENTS]
    variety_detail = {
        "recent_selection_events": [],
        "recent_selection_events_cap": MAX_SELECTION_EVENTS,
    }
    for e in recent_events:
        slug = slugify(e.exercise_name)
        ev_fact_id = f"variety:{slug}:{e.event_type}:{e.week}"
        _register(index, ev_fact_id,
                  "variety", e.exercise_name, e.event_type, e.week,
                  date=e.date)
        index.allowed_weeks.add(e.week)
        ev_entry = e.model_dump()
        ev_entry["fact_id"] = ev_fact_id
        variety_detail["recent_selection_events"].append(ev_entry)

    context = AIContext(
        profile=profile_dict,
        overview=overview_dict,
        prs=pr_dicts,
        progression_summary=prog_summaries,
        progression_detail=prog_detail,
        volume_summary=vol_summaries,
        volume_detail=vol_detail,
        plateaus=plateau_dicts,
        muscles=muscle_dicts,
        exercise_variety=variety_dict,
        exercise_variety_detail=variety_detail,
    )
    return context, index


__all__ = [
    "CONTEXT_VERSION",
    "MAX_SELECTION_EVENTS",
    "AIContext",
    "Fact",
    "GroundingIndex",
    "slugify",
    "detect_focus_exercise",
    "detect_focus_exercises",
    "build_ai_context",
]
