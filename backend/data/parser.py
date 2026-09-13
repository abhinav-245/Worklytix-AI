"""CSV parsing and column validation (step 1 of the pipeline).

Responsibilities:
- Decode the uploaded bytes and build the initial Pandas DataFrame.
- Preserve original column names/data (values are kept as strings so the
  cleaner can distinguish empty vs. invalid values deterministically).
- Validate required columns; unexpected columns are allowed and reported.

Raises:
    CSVParseError: file is empty, undecodable, or not parseable as CSV.
    MissingColumnsError: one or more required columns are absent.
"""

from __future__ import annotations

import io

import pandas as pd

# Core V1 fields. These must be present or the dataset cannot be normalized.
REQUIRED_COLUMNS = [
    "start_time",
    "exercise_title",
    "set_index",
    "set_type",
    "weight_kg",
    "reps",
]

# Supported but not required: mapped into the normalized model when present.
OPTIONAL_COLUMNS = [
    "end_time",
    "rpe",
    "title",
    "description",
    "superset_id",
    "exercise_notes",
    "distance_km",
    "duration_seconds",
]


class CSVPipelineError(Exception):
    """Base error for client-facing CSV pipeline failures (HTTP 400)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CSVParseError(CSVPipelineError):
    """The uploaded file could not be parsed as CSV."""


class MissingColumnsError(CSVPipelineError):
    """One or more required columns are missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "Missing required columns: " + ", ".join(f"'{c}'" for c in missing)
        )


def read_csv(data: bytes) -> pd.DataFrame:
    """Decode uploaded bytes into the initial DataFrame (all values as strings)."""
    if not data or not data.strip():
        raise CSVParseError("The uploaded file is empty.")

    try:
        text = data.decode("utf-8-sig")  # utf-8-sig also strips a BOM if present
    except UnicodeDecodeError as exc:
        raise CSVParseError("The file is not valid UTF-8 encoded CSV text.") from exc

    if not text.strip():
        raise CSVParseError("The uploaded file is empty.")

    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise CSVParseError("The uploaded file contains no CSV data.") from exc
    except pd.errors.ParserError as exc:
        raise CSVParseError(f"The file could not be parsed as CSV: {exc}") from exc

    # Normalize column labels (strip surrounding whitespace) but otherwise
    # preserve the original names/data exactly.
    df.columns = [str(c).strip() for c in df.columns]

    if df.columns.duplicated().any():
        dupes = sorted({c for c in df.columns if list(df.columns).count(c) > 1})
        raise CSVParseError(f"Duplicate column names found: {', '.join(dupes)}.")

    return df


def validate_columns(df: pd.DataFrame) -> list[str]:
    """Ensure required columns exist.

    Returns the list of unexpected (extra) columns, which are allowed and
    preserved for future use -- they never cause failure.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise MissingColumnsError(missing)

    known = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)
    return [c for c in df.columns if c not in known]
