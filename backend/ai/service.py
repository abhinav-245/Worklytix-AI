"""Gemini question-answering + recommendation service (Phase 12 + 13).

Flow per ask request (backend rebuilds everything from live in-memory
state)::

    question + bounded conversation + workouts + profile
        |
    deterministic focus-exercise detection + compact context build
        |
    Gemini (structured JSON via response_schema)
        |
    Pydantic parse + backend grounding validation
        |
    one corrective retry on violation, else controlled error

POST /ai/recommend reuses the same pipeline with a dedicated prompt and
response schema: goal + training-history classification come from the
authoritative backend profile, and recommendations are validated with
the same fact-ID/numeric grounding plus nutrition/medical safety
boundaries.

Uses ``client.models.generate_content`` from google-genai 2.x (the
supported interface in the installed SDK; the ``interactions`` attribute
exposes only generic resource stubs, not a conversational API).
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from typing import Any

from ai.config import GeminiConfig, load_gemini_config
from ai.context import (
    AIContext,
    GroundingIndex,
    build_ai_context,
    detect_focus_exercises,
)
from ai.knowledge import (
    UserSignals,
    format_knowledge,
    select_knowledge,
)
from ai.models import (
    AIResponse,
    AskRequest,
    ChatMessage,
    RecommendationResponse,
)
from ai.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    RECOMMENDATION_SYSTEM_PROMPT_V2,
    SYSTEM_PROMPT,
    build_analysis_message,
    build_correction_message,
    build_recommendation_v2_message,
    build_user_message,
    serialize_context,
)
from ai.validation import (
    validate_ai_response,
    validate_recommendation_response,
)
from analytics.profile import UserProfile, compute_training_history
from data.models import WorkoutRecord

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 2048
MAX_ANALYSIS_TOKENS = 4096
TEMPERATURE = 0.2
#: Cap on plateau records sent to the model. The deterministic engine
#: still computes every plateau and the grounding index still registers
#: every plateau fact; only the prompt payload is trimmed to the most
#: recent records so requests stay within provider context/rate limits.
MAX_ANALYSIS_PLATEAUS = 15


class AINotConfiguredError(Exception):
    """No GEMINI_API_KEY available server-side."""


class AIProviderError(Exception):
    """Gemini call failed or returned unusable output (details withheld)."""


def _get_client(config: GeminiConfig) -> Any:
    """Build the google-genai client (imported lazily for testability)."""
    from google.genai import Client

    return Client(api_key=config.api_key)


def _generate(
    client: Any,
    model: str,
    contents: list[dict[str, Any]],
    system_prompt: str = SYSTEM_PROMPT,
    response_schema: Any = AIResponse,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:
    """Call Gemini with structured JSON output; return raw text."""
    from google.genai import types

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=TEMPERATURE,
                max_output_tokens=max_output_tokens,
            ),
        )
    except Exception as exc:
        # Any SDK/transport failure becomes a controlled provider error.
        # Log class, message and traceback for diagnosis (never the API
        # key, never request secrets); the 502 response stays generic.
        logger.exception(
            "AI provider call failed: %s: %s",
            type(exc).__name__,
            str(exc),
        )
        raise AIProviderError("provider call failed") from exc
    text = (response.text or "").strip()
    if not text:
        raise AIProviderError("empty provider response")
    return text


def _parse_response(text: str, model: Any = AIResponse) -> Any:
    """Parse provider text into the validated response model."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIProviderError("unparseable provider response") from exc
    try:
        return model.model_validate(payload)
    except Exception as exc:
        raise AIProviderError("invalid provider response shape") from exc


def _conversation_turns(conversation: list[ChatMessage]) -> list[dict[str, Any]]:
    """Convert bounded history to Gemini roles (assistant -> model)."""
    turns: list[dict[str, Any]] = []
    for turn in conversation:
        role = "model" if turn.role == "assistant" else "user"
        turns.append({"role": role, "parts": [{"text": turn.content}]})
    return turns


def answer_question(
    request: AskRequest,
    workouts: list[WorkoutRecord],
    profile: UserProfile | None,
    config: GeminiConfig | None = None,
    client: Any | None = None,
) -> AIResponse:
    """Answer one question against live analytics; validated or error."""
    cfg = config or load_gemini_config()
    if not cfg.is_configured:
        raise AINotConfiguredError("Gemini API key is not configured")
    active_client = client if client is not None else _get_client(cfg)

    exercise_names = sorted(
        {
            e.exercise_name
            for w in workouts
            for e in w.exercises
            if e.exercise_name and e.exercise_name.strip()
        }
    )
    focus = detect_focus_exercises(request.question, exercise_names)
    context, index = build_ai_context(workouts, profile, focus)

    contents = _conversation_turns(request.conversation) + [
        {
            "role": "user",
            "parts": [
                {
                    "text": build_user_message(
                        request.question,
                        serialize_context(context),
                        [
                            {"role": t.role, "content": t.content}
                            for t in request.conversation
                        ],
                    )
                }
            ],
        }
    ]

    problems: list[str] = []
    try:
        text = _generate(active_client, cfg.model, contents)
        parsed = _parse_response(text)
    except AIProviderError:
        # One plain retry for call/parse failures before giving up.
        try:
            text = _generate(active_client, cfg.model, contents)
            parsed = _parse_response(text)
        except AIProviderError as exc:
            logger.warning("AI provider call failed: %s", type(exc).__name__)
            raise

    problems = validate_ai_response(parsed, index)
    if problems:
        try:
            retry_contents = contents + [
                {
                    "role": "user",
                    "parts": [{"text": build_correction_message(problems)}],
                }
            ]
            retry_text = _generate(active_client, cfg.model, retry_contents)
            retry_parsed = _parse_response(retry_text)
            retry_problems = validate_ai_response(retry_parsed, index)
        except AIProviderError as exc:
            logger.warning("AI corrective retry failed: %s", type(exc).__name__)
            raise
        if retry_problems:
            logger.warning(
                "AI response failed grounding validation after retry"
            )
            raise AIProviderError("unvalidated provider response")
        return retry_parsed
    return parsed


def _plateau_end_value(entry: dict[str, Any]) -> str:
    """Unwrap a (possibly fact-cited) plateau_end for recency sorting."""
    end = entry.get("plateau_end")
    if isinstance(end, dict):
        value = end.get("value")
        return value if isinstance(value, str) else ""
    return end if isinstance(end, str) else ""


def trim_context_for_model(context: AIContext) -> AIContext:
    """Return a copy with plateau records capped to the most recent.

    Presentation-layer trim only: analytics and the grounding index are
    untouched, so any plateau fact remains citable if visible.
    Deterministic (sorts by plateau_end, then exercise name).
    """
    ranked = sorted(
        context.plateaus,
        key=lambda e: (
            _plateau_end_value(e),
            e.get("exercise_name") if isinstance(e, dict) else "",
        ),
        reverse=True,
    )
    return context.model_copy(
        update={"plateaus": ranked[:MAX_ANALYSIS_PLATEAUS]}
    )


def _history_summary(workouts: list[WorkoutRecord]) -> str:
    """Authoritative training-history classification as prompt text."""
    history = compute_training_history(workouts)
    if history is None:
        return "unknown (no dated workouts)"
    return (
        f"{history.level} ({history.duration_text}, "
        f"{history.start_date} to {history.end_date})"
    )


def _user_signals(
    profile: UserProfile, index: GroundingIndex
) -> UserSignals:
    """Read-only deterministic signals for knowledge selection."""
    level = "Beginner"
    for fid, fact in index.facts.items():
        if fid == "profile:level" and isinstance(fact.value, str):
            level = fact.value
    has_plateau = any(
        fid.startswith("plateau:") for fid in index.facts
    )
    low_frequency = False
    freq_fact = index.facts.get("overview:dataset:workouts_per_week")
    if (
        freq_fact is not None
        and isinstance(freq_fact.value, (int, float))
        and freq_fact.value < 2
    ):
        low_frequency = True
    return UserSignals(
        goal=profile.goal,
        level=level,
        has_plateau=has_plateau,
        low_frequency=low_frequency,
    )


def _fact_id_suggestions(
    problems: list[str], index: GroundingIndex, limit: int = 3
) -> list[str]:
    """Suggest closest registered IDs for unknown-ID violations.

    Gives the corrective retry precise, machine-checked candidates
    instead of a vague "fix grounding" instruction. Suggestions only;
    validation still requires exact matches.
    """
    unknown = dict.fromkeys(
        re.findall(r"cites unknown fact ID '([^']+)'", "\n".join(problems))
    )
    registered = list(index.facts.keys())
    categories = sorted({fid.split(":")[0] for fid in registered})
    hints: list[str] = []
    for bad_id in unknown:
        close = difflib.get_close_matches(
            bad_id, registered, n=limit, cutoff=0.3
        )
        if close:
            hints.append(
                f"Invalid fact ID {bad_id!r}; did you mean one of: "
                + ", ".join(repr(c) for c in close)
                + "? Copy the exact ID from the analytics context."
            )
        else:
            hints.append(
                f"Invalid fact ID {bad_id!r}; no close match exists. "
                "Valid IDs have the form 'category:subject:metric' "
                f"(categories in this context: {', '.join(categories)}). "
                "Copy one exactly from the analytics context; never "
                "invent or shorten IDs."
            )
    return hints


def _log_problems(stage: str, problems: list[str], limit: int = 10) -> None:
    """Log concise grounding diagnostics (fact IDs/values only, no secrets)."""
    shown = problems[:limit]
    extra = f" (+{len(problems) - limit} more)" if len(problems) > limit else ""
    logger.warning(
        "%s grounding problems (%d): %s%s",
        stage, len(problems), "; ".join(shown), extra,
    )


def _generate_validated(
    client: Any,
    model: str,
    contents: list[dict[str, Any]],
    index: GroundingIndex,
    *,
    system_prompt: str,
    schema: Any,
    validate: Any,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    retry_label: str = "AI response",
) -> Any:
    """Generate + parse + ground with one plain and one corrective retry."""
    generate_kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "response_schema": schema,
        "max_output_tokens": max_output_tokens,
    }
    try:
        text = _generate(client, model, contents, **generate_kwargs)
        parsed = _parse_response(text, schema)
    except AIProviderError:
        # One plain retry for call/parse failures before giving up.
        try:
            text = _generate(client, model, contents, **generate_kwargs)
            parsed = _parse_response(text, schema)
        except AIProviderError as exc:
            logger.warning("AI provider call failed: %s", type(exc).__name__)
            raise

    problems = validate(parsed, index)
    if problems:
        _log_problems(f"{retry_label} first attempt", problems)
        try:
            correction = build_correction_message(problems)
            hints = _fact_id_suggestions(problems, index)
            if hints:
                correction += "\n" + "\n".join(f"- {h}" for h in hints)
            retry_contents = contents + [
                {
                    "role": "user",
                    "parts": [{"text": correction}],
                }
            ]
            retry_text = _generate(
                client, model, retry_contents, **generate_kwargs
            )
            retry_parsed = _parse_response(retry_text, schema)
            retry_problems = validate(retry_parsed, index)
        except AIProviderError as exc:
            logger.warning("AI corrective retry failed: %s", type(exc).__name__)
            raise
        if retry_problems:
            _log_problems(f"{retry_label} retry", retry_problems)
            logger.warning("%s failed grounding validation after retry",
                           retry_label)
            raise AIProviderError("unvalidated provider response")
        return retry_parsed
    return parsed


def analyze_training(
    workouts: list[WorkoutRecord],
    profile: UserProfile,
    config: GeminiConfig | None = None,
    client: Any | None = None,
) -> AIResponse:
    """Generate the comprehensive initial training analysis."""
    cfg = config or load_gemini_config()
    if not cfg.is_configured:
        raise AINotConfiguredError("Gemini API key is not configured")
    active_client = client if client is not None else _get_client(cfg)

    context, index = build_ai_context(workouts, profile, [])
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": build_analysis_message(
                        profile.goal,
                        _history_summary(workouts),
                        serialize_context(
                            trim_context_for_model(context)
                        ),
                    )
                }
            ],
        }
    ]
    return _generate_validated(
        active_client, cfg.model, contents, index,
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        schema=AIResponse,
        validate=validate_ai_response,
        max_output_tokens=MAX_ANALYSIS_TOKENS,
        retry_label="AI analysis",
    )


def build_analysis_contents(
    workouts: list[WorkoutRecord],
    profile: UserProfile,
) -> tuple[list[dict[str, Any]], GroundingIndex, AIContext]:
    """Build the analysis request (test/support helper)."""
    context, index = build_ai_context(workouts, profile, [])
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": build_analysis_message(
                        profile.goal,
                        _history_summary(workouts),
                        serialize_context(
                            trim_context_for_model(context)
                        ),
                    )
                }
            ],
        }
    ]
    return contents, index, context


def build_recommendation_contents(
    workouts: list[WorkoutRecord],
    profile: UserProfile,
    analysis: str,
) -> tuple[list[dict[str, Any]], GroundingIndex, AIContext]:
    """Build the v2 recommendation request from backend state.

    Goal and training-history classification come from the authoritative
    backend profile (never the frontend). The prior analysis text is
    conversational context only. Knowledge items are general principles,
    not user facts. Summaries are used without per-point detail to keep
    the context compact.
    """
    context, index = build_ai_context(workouts, profile, [])
    knowledge = select_knowledge(_user_signals(profile, index))
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": build_recommendation_v2_message(
                        profile.goal,
                        _history_summary(workouts),
                        analysis,
                        format_knowledge(knowledge),
                        serialize_context(
                            trim_context_for_model(context)
                        ),
                    )
                }
            ],
        }
    ]
    return contents, index, context


def recommend_training(
    workouts: list[WorkoutRecord],
    profile: UserProfile,
    analysis: str,
    config: GeminiConfig | None = None,
    client: Any | None = None,
) -> RecommendationResponse:
    """Generate personalized recommendations; validated or error."""
    cfg = config or load_gemini_config()
    if not cfg.is_configured:
        raise AINotConfiguredError("Gemini API key is not configured")
    active_client = client if client is not None else _get_client(cfg)

    contents, index, _ = build_recommendation_contents(
        workouts, profile, analysis
    )
    return _generate_validated(
        active_client, cfg.model, contents, index,
        system_prompt=RECOMMENDATION_SYSTEM_PROMPT_V2,
        schema=RecommendationResponse,
        validate=validate_recommendation_response,
        retry_label="AI recommendation",
    )


def grounding_index_for_request(
    workouts: list[WorkoutRecord],
    profile: UserProfile | None,
    question: str,
) -> GroundingIndex:
    """Build only the grounding index (test/support helper)."""
    names = sorted(
        {
            e.exercise_name
            for w in workouts
            for e in w.exercises
            if e.exercise_name and e.exercise_name.strip()
        }
    )
    _, index = build_ai_context(
        workouts, profile, detect_focus_exercises(question, names)
    )
    return index


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "MAX_ANALYSIS_TOKENS",
    "MAX_ANALYSIS_PLATEAUS",
    "TEMPERATURE",
    "AINotConfiguredError",
    "AIProviderError",
    "answer_question",
    "analyze_training",
    "trim_context_for_model",
    "build_analysis_contents",
    "build_recommendation_contents",
    "recommend_training",
    "grounding_index_for_request",
]
