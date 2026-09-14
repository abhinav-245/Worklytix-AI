"""Backend grounding validation (Phase 12 ask + Phase 13 recommend).

Prompt text alone is never trusted. Every structured Gemini response is
checked here before it can reach the API:

1. Every observation references at least one known fact ID.
2. Every referenced fact ID exists in the backend registry.
3. Numbers with units, decimals, percentages, dates and ISO weeks inside
   factual statements (answer + observations, plus Phase 13
   recommendation/reason texts) must appear in the analytics
   context. Bare integers without units are ignored to avoid rejecting
   harmless prose ("here are your top lifts").
4. Assumptions and limitations are interpretive by design and are NOT
   numeric-validated (hypothetical numbers like "what if you did 5 more
   reps" must not false-positive).
5. Phase 13 recommendations additionally reject unsupported nutrition
   and medical/diagnosis claims (FIT-INTEL tracks neither).

The backend remains the final authority: any violation rejects the
response (with one corrective retry attempted by the service layer).
"""

from __future__ import annotations

import re

from ai.context import GroundingIndex
from ai.models import AIResponse, RecommendationResponse

_DATE_FIND = re.compile(r"\d{4}-\d{2}-\d{2}")
_WEEK_FIND = re.compile(r"\d{4}-W\d{2}")
_NUMBER_UNIT_FIND = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
    r"(kg|reps?|sets?|workouts?|weeks?|days?|years?|months?|min\b|"
    r"percent|%|×|/wk\b)",
    re.IGNORECASE,
)
_DECIMAL_FIND = re.compile(r"\d{1,3}(?:,\d{3})+|\d+\.\d+")

#: Phase 13 safety denylist (checked in recommendation/reason/observation
#: texts only -- assumptions and limitations stay exempt so unavailable
#: data can be named, e.g. "the dataset has no protein data"). FIT-INTEL
#: tracks no nutrition and makes no medical claims.
_UNSAFE_NUTRITION_FIND = re.compile(
    r"\b(protein|creatine|calories?|kcal|macros?|supplements?)\b",
    re.IGNORECASE,
)
_UNSAFE_MEDICAL_FIND = re.compile(
    r"\b(diagnos\w*|prescri\w*|medications?|treatments?)\b",
    re.IGNORECASE,
)


def _numbers_requiring_grounding(text: str) -> tuple[list[str], list[float], list[float]]:
    """Extract (dates, weeks, numbers) that must exist in the context.

    Dates and ISO weeks are extracted first and removed so their digit
    runs (e.g. the 09 in 2026-09-11) are never double-checked.
    Thousands separators are stripped before number extraction so a
    grounded value like "3,274,475.1 kg" is checked as 3274475.1 --
    not fragmented into 3274475.0 plus a phantom 475.1.
    """
    dates = _DATE_FIND.findall(text)
    weeks = _WEEK_FIND.findall(text)
    scrubbed = _DATE_FIND.sub(" ", text)
    scrubbed = _WEEK_FIND.sub(" ", scrubbed)
    scrubbed = re.sub(r"(?<=\d),(?=\d)", "", scrubbed)
    numbers: list[float] = []
    for match in _NUMBER_UNIT_FIND.finditer(scrubbed):
        numbers.append(float(match.group(1).replace(",", "")))
    for match in _DECIMAL_FIND.finditer(scrubbed):
        numbers.append(float(match.group(0).replace(",", "")))
    return dates, weeks, numbers


def validate_ai_response(
    response: AIResponse, index: GroundingIndex
) -> list[str]:
    """Return a list of grounding problems (empty means valid)."""
    problems: list[str] = []

    for i, obs in enumerate(response.observations):
        if not obs.fact_ids:
            problems.append(
                f"Observation {i + 1} has no fact IDs; every factual "
                "observation must cite at least one supplied fact."
            )
            continue
        for fact_id in obs.fact_ids:
            if fact_id not in index.facts:
                problems.append(
                    f"Observation {i + 1} cites unknown fact ID "
                    f"{fact_id!r}; only supplied fact IDs may be used."
                )

    factual_texts = [response.answer] + [
        obs.statement for obs in response.observations
    ]
    for label, text in [("answer", factual_texts[0])] + [
        (f"observation {i + 1}", s)
        for i, s in enumerate(factual_texts[1:])
    ]:
        dates, weeks, numbers = _numbers_requiring_grounding(text)
        for token in dates:
            if token not in index.allowed_dates:
                problems.append(
                    f"{label} mentions date {token} which does not appear "
                    "in the analytics context."
                )
        for token in weeks:
            if token not in index.allowed_weeks:
                problems.append(
                    f"{label} mentions week {token} which does not appear "
                    "in the analytics context."
                )
        for number in numbers:
            if number not in index.allowed_numbers:
                problems.append(
                    f"{label} mentions value {number:g} which does not "
                    "appear in the analytics context."
                )
    return problems


def _check_fact_ids(
    items: list[tuple[str, list[str]]], index: GroundingIndex
) -> list[str]:
    """Validate (label, fact_ids) pairs against the backend registry."""
    problems: list[str] = []
    for label, fact_ids in items:
        if not fact_ids:
            problems.append(
                f"{label} has no fact IDs; every factual "
                "statement must cite at least one supplied fact."
            )
            continue
        for fact_id in fact_ids:
            if fact_id not in index.facts:
                problems.append(
                    f"{label} cites unknown fact ID "
                    f"{fact_id!r}; only supplied fact IDs may be used."
                )
    return problems


def _check_grounded_numbers(
    labeled_texts: list[tuple[str, str]], index: GroundingIndex
) -> list[str]:
    """Validate dates/weeks/numbers in factual texts against the context."""
    problems: list[str] = []
    for label, text in labeled_texts:
        dates, weeks, numbers = _numbers_requiring_grounding(text)
        for token in dates:
            if token not in index.allowed_dates:
                problems.append(
                    f"{label} mentions date {token} which does not appear "
                    "in the analytics context."
                )
        for token in weeks:
            if token not in index.allowed_weeks:
                problems.append(
                    f"{label} mentions week {token} which does not appear "
                    "in the analytics context."
                )
        for number in numbers:
            if number not in index.allowed_numbers:
                problems.append(
                    f"{label} mentions value {number:g} which does not "
                    "appear in the analytics context."
                )
    return problems


def validate_recommendation_response(
    response: RecommendationResponse, index: GroundingIndex
) -> list[str]:
    """Validate a Phase 13 recommendation response (empty means valid).

    Observations and recommendation reasoning must cite exact registered
    fact IDs and contain only grounded numbers/dates. The recommendation
    suggestion itself need not literally exist in the analytics, but its
    factual reasoning must. Unsupported nutrition/medical claims are
    rejected; assumptions and limitations stay exempt.
    """
    problems: list[str] = []
    problems.extend(_check_fact_ids(
        [
            (f"Observation {i + 1}", obs.fact_ids)
            for i, obs in enumerate(response.observations)
        ]
        + [
            (f"Recommendation {i + 1}", rec.fact_ids)
            for i, rec in enumerate(response.recommendations)
        ],
        index,
    ))
    factual_texts = (
        [(f"Observation {i + 1}", o.statement)
         for i, o in enumerate(response.observations)]
        + [(f"Recommendation {i + 1}", r.recommendation)
           for i, r in enumerate(response.recommendations)]
        + [(f"Recommendation {i + 1} reason", r.reason)
           for i, r in enumerate(response.recommendations)]
    )
    problems.extend(_check_grounded_numbers(factual_texts, index))
    for label, text in factual_texts:
        if _UNSAFE_NUTRITION_FIND.search(text):
            problems.append(
                f"{label} contains nutrition guidance, but FIT-INTEL "
                "tracks no nutrition data."
            )
        if _UNSAFE_MEDICAL_FIND.search(text):
            problems.append(
                f"{label} contains a medical/diagnosis claim, which "
                "FIT-INTEL cannot make."
            )
    return problems


__all__ = ["validate_ai_response", "validate_recommendation_response"]
