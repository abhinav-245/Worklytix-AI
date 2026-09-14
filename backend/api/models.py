"""Standardized analytics API envelope (Phase 10).

Every analytics endpoint returns::

    {
      "success": True,
      "data": { ... domain-specific payload ... },
      "meta": { "analysis_version": "v1" },
    }

``data`` keeps each endpoint's established domain shape (e.g. progression
keeps ``{"exercises": [...]}``); only the PR list endpoint gains a thin
``{"exercises": [...]}`` wrapper so it is an object like the others.
``meta`` carries only the versioned contract string -- analytics remain
free of current-time dependence. Application errors (missing dataset,
unknown exercise) keep the established 404 ``detail`` convention, and
request-validation failures keep FastAPI's standard 422 responses.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from analytics.prs import ExercisePR

#: Version string for the standardized analytics contract.
ANALYSIS_VERSION = "v1"

T = TypeVar("T")


class APIMeta(BaseModel):
    """Envelope metadata (contract version only, no analytics input)."""

    analysis_version: str = Field(
        default=ANALYSIS_VERSION,
        description="Versioned analytics API contract.",
    )


class APIResponse(BaseModel, Generic[T]):
    """Standard success envelope wrapping a domain-specific payload."""

    success: bool = Field(
        default=True, description="True for successful analytics responses."
    )
    data: T = Field(description="Domain-specific analytics payload.")
    meta: APIMeta = Field(default_factory=APIMeta)


class PRListData(BaseModel):
    """Object wrapper so GET /analysis/prs matches the envelope contract."""

    exercises: list[ExercisePR] = Field(default_factory=list)


def wrap(data: T) -> APIResponse[T]:
    """Wrap a domain payload in the standard success envelope."""
    return APIResponse(data=data)


__all__ = [
    "ANALYSIS_VERSION",
    "APIMeta",
    "APIResponse",
    "PRListData",
    "wrap",
]
