"""Data cleaning (step 2 of the pipeline).

Responsibilities:
- Numeric parsing (set_index, weight_kg, reps, rpe, distance_km, duration_seconds)
- Date/time parsing (start_time, end_time)
- set_type normalization
- Deciding which rows are usable, with deterministic, documented rules.

Rules (deterministic):
- Empty numeric/date values -> missing (counted in ``missing_values``).
- Non-empty but unparseable numeric/date values -> invalid (counted in
  ``invalid_values``); the value becomes null, never a misleading number.
  In particular, missing weight/reps are NEVER treated as zero.
- A row is dropped (counted in ``invalid_rows`` with reasons) only when it
  lacks the identity needed to place it in the Workout -> Exercise -> Set
  hierarchy: an empty ``exercise_title`` or a missing/invalid ``start_time``.
- ``set_type`` is normalized via SET_TYPE_MAP. Empty values become
  ``"unknown"`` and unrecognized values become ``"unknown:<token>"`` -- they
  are counted in ``invalid_values["set_type"]`` but never silently mapped to
  ``"normal"``, and the row is kept.

Actual Hevy values observed (backend/tests/fixtures/workout_data.csv):
``normal``, ``warmup``, ``dropset``, ``failure`` (all lowercase).
Timestamps look like ``"12 Sep 2026, 17:56"`` (timezone-naive, no seconds).
The mapping below additionally covers common variants (``warm-up``,
``warm up``, ``drop set``, ...) so the rules stay deterministic if they occur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .models import DroppedRow

#: Hevy export timestamp format, e.g. "12 Sep 2026, 17:56".
HEVY_DATETIME_FORMAT = "%d %b %Y, %H:%M"

#: Normalized set types that future analytics may rely on.
KNOWN_SET_TYPES = {"normal", "warm_up", "drop_set", "failure"}

#: Raw (case/whitespace/punctuation-insensitive) -> normalized set type.
SET_TYPE_MAP = {
    "normal": "normal",
    "warmup": "warm_up",
    "warm_up": "warm_up",
    "warm-up": "warm_up",
    "warm up": "warm_up",
    "dropset": "drop_set",
    "drop_set": "drop_set",
    "drop-set": "drop_set",
    "drop set": "drop_set",
    "drop": "drop_set",
    "failure": "failure",
}

#: Numeric columns parsed by the cleaner (all optional at row level).
NUMERIC_COLUMNS = [
    "set_index",
    "weight_kg",
    "reps",
    "rpe",
    "distance_km",
    "duration_seconds",
]

#: Columns whose cleaned values end up in the normalized model.
TEXT_COLUMNS = [
    "title",
    "description",
    "exercise_title",
    "exercise_notes",
    "superset_id",
]


@dataclass
class CleanedData:
    """Result of cleaning: usable rows plus data-quality counters."""

    frame: pd.DataFrame
    total_rows: int
    missing_values: dict[str, int] = field(default_factory=dict)
    invalid_values: dict[str, int] = field(default_factory=dict)
    dropped_rows: list[DroppedRow] = field(default_factory=list)


def _clean_text(value: object) -> str:
    """Strip a raw string cell; non-strings become ''."""
    return value.strip() if isinstance(value, str) else ""


def normalize_set_type(raw: object) -> str:
    """Normalize a raw set_type value deterministically (never returns '')."""
    token = _clean_text(raw).lower().replace("-", " ").split()
    token = "_".join(token)
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        return "unknown"
    if token in SET_TYPE_MAP:
        return SET_TYPE_MAP[token]
    if token in KNOWN_SET_TYPES:
        return token
    return f"unknown:{token}"


def _parse_number(raw: object) -> tuple[int | float | None, str]:
    """Parse one numeric cell.

    Returns (value, status) where status is 'ok', 'missing' or 'invalid'.
    Integral values become int, fractional values stay float -- deterministic
    and lossless for the magnitudes in workout data.
    """
    text = _clean_text(raw)
    if text == "":
        return None, "missing"
    try:
        number = float(text)
    except ValueError:
        return None, "invalid"
    if number.is_integer():
        return int(number), "ok"
    return number, "ok"


def _parse_datetimes(raw: pd.Series) -> pd.Series:
    """Parse a datetime column; unparseable non-empty values become NaT.

    Tries the Hevy format first, then falls back to flexible parsing so other
    app exports keep working. Timezones are preserved when present; naive
    timestamps stay naive (no timezone is invented). If a column mixes naive
    and aware timestamps, all are unified to UTC so rows stay comparable.
    """
    text = raw.map(_clean_text)
    parsed = pd.to_datetime(text, format=HEVY_DATETIME_FORMAT, errors="coerce")
    needs_retry = parsed.isna() & (text != "")
    if needs_retry.any():
        parsed.loc[needs_retry] = pd.to_datetime(
            text[needs_retry], errors="coerce", utc=False
        )
    return _unify_timezones(parsed)


def _unify_timezones(parsed: pd.Series) -> pd.Series:
    """Unify a parsed datetime column to all-naive or all-UTC (deterministic)."""
    stamps = [t for t in parsed.dropna() if isinstance(t, pd.Timestamp)]
    has_aware = any(t.tzinfo is not None for t in stamps)
    has_naive = any(t.tzinfo is None for t in stamps)
    if has_aware and has_naive:
        return parsed.map(
            lambda t: (
                t
                if not isinstance(t, pd.Timestamp) or pd.isna(t)
                else (
                    t.tz_convert("UTC")
                    if t.tzinfo is not None
                    else t.tz_localize("UTC")
                )
            )
        )
    return parsed


def clean_dataframe(df: pd.DataFrame, extra_columns: list[str]) -> CleanedData:
    """Clean the raw DataFrame into normalized columns + quality counters."""
    total_rows = len(df)
    missing: dict[str, int] = {}
    invalid: dict[str, int] = {}

    cleaned = pd.DataFrame(index=df.index)
    cleaned["__line__"] = df.index + 2  # 1-based CSV line number (header = line 1)

    for col in TEXT_COLUMNS:
        cleaned[col] = df[col].map(_clean_text) if col in df.columns else ""

    # Numeric columns: None for missing/invalid at this stage.
    raw_numbers: dict[str, pd.Series] = {}
    for col in NUMERIC_COLUMNS:
        source = df[col] if col in df.columns else pd.Series("", index=df.index)
        parsed = source.map(_parse_number)
        values = parsed.map(lambda p: p[0])
        statuses = parsed.map(lambda p: p[1])
        missing[col] = int((statuses == "missing").sum())
        invalid[col] = int((statuses == "invalid").sum())
        raw_numbers[col] = values

    cleaned["set_index"] = raw_numbers["set_index"]
    for col in ("weight_kg", "reps", "rpe", "distance_km", "duration_seconds"):
        cleaned[col] = raw_numbers[col].map(
            lambda v: None if v is None else float(v)
        )

    # set_type normalization (required column, always present after validation).
    raw_types = df["set_type"].map(_clean_text)
    cleaned["set_type"] = df["set_type"].map(normalize_set_type)
    bad_types = (cleaned["set_type"] == "unknown") | cleaned[
        "set_type"
    ].str.startswith("unknown:")
    missing["set_type"] = int((raw_types == "").sum())
    invalid["set_type"] = int(((raw_types != "") & bad_types).sum())

    # Date/time parsing.
    start = _parse_datetimes(df["start_time"])
    cleaned["start_time"] = start
    start_text = df["start_time"].map(_clean_text)
    missing["start_time"] = int((start_text == "").sum())
    invalid["start_time"] = int(((start_text != "") & start.isna()).sum())

    if "end_time" in df.columns:
        end = _parse_datetimes(df["end_time"])
        cleaned["end_time"] = end
        missing["end_time"] = int((df["end_time"].map(_clean_text) == "").sum())
        invalid["end_time"] = int(
            ((df["end_time"].map(_clean_text) != "") & end.isna()).sum()
        )
    else:
        cleaned["end_time"] = pd.NaT
        missing["end_time"] = total_rows
        invalid["end_time"] = 0

    missing["exercise_title"] = int((cleaned["exercise_title"] == "").sum())
    invalid["exercise_title"] = 0

    # Preserve non-empty values of unexpected columns per row.
    extras: list[dict[str, str]] = []
    for _, row in df.iterrows():
        entry = {}
        for col in extra_columns:
            value = _clean_text(row[col])
            if value != "":
                entry[col] = value
        extras.append(entry)
    cleaned["extra"] = extras

    # Row validity: a row must be placeable in Workout -> Exercise -> Set.
    dropped: list[DroppedRow] = []
    valid_mask = pd.Series(True, index=df.index)
    for idx in df.index:
        reasons: list[str] = []
        if cleaned.at[idx, "exercise_title"] == "":
            reasons.append("missing exercise_title")
        if pd.isna(cleaned.at[idx, "start_time"]):
            if _clean_text(df.at[idx, "start_time"]) == "":
                reasons.append("missing start_time")
            else:
                reasons.append(
                    f"invalid start_time: {df.at[idx, 'start_time']!r}"
                )
        if reasons:
            valid_mask.at[idx] = False
            dropped.append(
                DroppedRow(row_number=int(cleaned.at[idx, "__line__"]), reasons=reasons)
            )

    valid_frame = cleaned[valid_mask].copy()
    return CleanedData(
        frame=valid_frame,
        total_rows=total_rows,
        missing_values=missing,
        invalid_values=invalid,
        dropped_rows=dropped,
    )
