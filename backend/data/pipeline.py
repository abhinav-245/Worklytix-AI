"""Pipeline orchestration: parser -> cleaner -> normalizer -> response.

Single entry point used by the API layer (``main.py``) and by tests::

    Upload bytes
        |
    read_csv (parse)
        |
    validate_columns
        |
    clean_dataframe (clean)
        |
    build_workouts + compute_statistics (normalize)
        |
    UploadResponse
"""

from .cleaner import clean_dataframe
from .models import UploadResponse
from .normalizer import build_workouts, compute_statistics
from .parser import read_csv, validate_columns


def process_csv_bytes(data: bytes) -> UploadResponse:
    """Run the full CSV pipeline in memory and return the API response."""
    df = read_csv(data)
    extra_columns = validate_columns(df)
    cleaned = clean_dataframe(df, extra_columns)
    workouts = build_workouts(cleaned.frame)
    statistics = compute_statistics(cleaned, workouts, extra_columns)
    return UploadResponse(statistics=statistics, workouts=workouts)
