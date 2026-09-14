"""AI interpretation layer (Phase 12).

Deterministic analytics remain the source of truth; this package only
interprets them via Gemini 2.5 Flash::

    CSV -> Parser / Cleaner / Normalizer -> Deterministic Analytics
        -> Structured AI Context (+ stable fact IDs)
        -> Gemini 2.5 Flash (structured JSON output)
        -> Pydantic parse + backend grounding validation
        -> Structured AI Interpretation

Nothing here calculates analytics. The LLM never sees the raw CSV.
"""

from ai.config import GeminiConfig, load_gemini_config
from ai.context import (
    AIContext,
    GroundingIndex,
    build_ai_context,
    detect_focus_exercise,
)
from ai.models import (
    AIAssumption,
    AIObservation,
    AIResponse,
    AIResponseData,
    AskRequest,
    ChatMessage,
)
from ai.prompts import SYSTEM_PROMPT
from ai.service import (
    AINotConfiguredError,
    AIProviderError,
    answer_question,
)
from ai.validation import validate_ai_response

__all__ = [
    "GeminiConfig",
    "load_gemini_config",
    "AIContext",
    "GroundingIndex",
    "build_ai_context",
    "detect_focus_exercise",
    "AIAssumption",
    "AIObservation",
    "AIResponse",
    "AIResponseData",
    "AskRequest",
    "ChatMessage",
    "SYSTEM_PROMPT",
    "AINotConfiguredError",
    "AIProviderError",
    "answer_question",
    "validate_ai_response",
]
