"""AI request/response models (Phase 12 ask + Phase 13 recommend).

- ``AskRequest`` validates the user question and bounded conversation.
- ``AIResponse`` is BOTH the Gemini structured-output schema
  (``response_schema``) AND the backend-validated interpretation.
- ``AIResponseData`` is the ``data`` payload inside the standard
  ``{success, data, meta}`` envelope.
- ``RecommendationResponse`` / ``RecommendationResponseData`` are the
  Phase 13 equivalents for POST /ai/recommend: grounded observations
  plus explicitly-labeled optional recommendations (suggestions, never
  deterministic facts).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_QUESTION_LENGTH = 2000
MAX_CONVERSATION_MESSAGES = 20
MAX_MESSAGE_LENGTH = 2000


class ChatMessage(BaseModel):
    """One bounded conversation turn (continuity only, never facts)."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("content", mode="before")
    @classmethod
    def _strip_content(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class AskRequest(BaseModel):
    """POST /ai/ask request body."""

    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    conversation: list[ChatMessage] = Field(
        default_factory=list, max_length=MAX_CONVERSATION_MESSAGES
    )

    @field_validator("question", mode="before")
    @classmethod
    def _strip_question(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class AIObservation(BaseModel):
    """A factual statement grounded in one or more fact IDs."""

    statement: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1)


class AIAssumption(BaseModel):
    """A possible interpretation, explicitly NOT proven by the dataset."""

    statement: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AIResponse(BaseModel):
    """Structured Gemini output: answer + grounded observations."""

    answer: str = Field(min_length=1)
    observations: list[AIObservation] = Field(default_factory=list)
    assumptions: list[AIAssumption] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AIResponseData(BaseModel):
    """``data`` payload of the POST /ai/ask envelope response."""

    answer: str
    observations: list[AIObservation] = Field(default_factory=list)
    assumptions: list[AIAssumption] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


MAX_ANALYSIS_LENGTH = 12000


class RecommendRequest(BaseModel):
    """POST /ai/recommend request body: prior analysis as context only."""

    analysis: str = Field(min_length=1, max_length=MAX_ANALYSIS_LENGTH)

    @field_validator("analysis", mode="before")
    @classmethod
    def _strip_analysis(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class AIRecommendation(BaseModel):
    """One optional suggestion plus its grounded factual reasoning."""

    recommendation: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1)


class RecommendationResponse(BaseModel):
    """Structured Gemini output for POST /ai/recommend."""

    recommendations: list[AIRecommendation] = Field(default_factory=list)
    observations: list[AIObservation] = Field(default_factory=list)
    assumptions: list[AIAssumption] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RecommendationResponseData(BaseModel):
    """``data`` payload of the POST /ai/recommend envelope response."""

    recommendations: list[AIRecommendation] = Field(default_factory=list)
    observations: list[AIObservation] = Field(default_factory=list)
    assumptions: list[AIAssumption] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


__all__ = [
    "MAX_QUESTION_LENGTH",
    "MAX_CONVERSATION_MESSAGES",
    "MAX_MESSAGE_LENGTH",
    "MAX_ANALYSIS_LENGTH",
    "ChatMessage",
    "AskRequest",
    "RecommendRequest",
    "AIObservation",
    "AIAssumption",
    "AIResponse",
    "AIResponseData",
    "AIRecommendation",
    "RecommendationResponse",
    "RecommendationResponseData",
]
