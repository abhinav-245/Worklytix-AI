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

from ai.models import AIResponseData, RecommendationResponseData
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


class AIAPIMeta(BaseModel):
    """Envelope metadata for AI responses: contract version plus model."""

    analysis_version: str = Field(
        default=ANALYSIS_VERSION,
        description="Versioned analytics API contract.",
    )
    model: str = Field(description="Provider model that produced the answer.")


class AIAPIResponse(BaseModel):
    """Standard success envelope for POST /ai/ask."""

    success: bool = Field(
        default=True, description="True for successful AI responses."
    )
    data: AIResponseData = Field(description="Validated AI interpretation.")
    meta: AIAPIMeta = Field(description="Contract version and model name.")


class RecommendAPIResponse(BaseModel):
    """Standard success envelope for POST /ai/recommend."""

    success: bool = Field(
        default=True, description="True for successful AI responses."
    )
    data: RecommendationResponseData = Field(
        description="Validated optional recommendations."
    )
    meta: AIAPIMeta = Field(description="Contract version and model name.")


def wrap(data: T) -> APIResponse[T]:
    """Wrap a domain payload in the standard success envelope."""
    return APIResponse(data=data)


__all__ = [
    "ANALYSIS_VERSION",
    "APIMeta",
    "APIResponse",
    "PRListData",
    "AIAPIMeta",
    "AIAPIResponse",
    "RecommendAPIResponse",
    "wrap",
]
