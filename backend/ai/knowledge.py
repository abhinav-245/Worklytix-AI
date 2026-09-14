"""Curated training-knowledge base (AI-first experience).

Small, hand-reviewed set of general training principles used by the
recommendation engine (SOURCE 2) alongside user-specific evidence
(SOURCE 1). Principles are NEVER user facts: they carry no fact IDs,
no numbers about the user, and must not be cited as observations.

The abstraction is deliberately tiny so a future database/RAG source
can replace ``KNOWLEDGE_ITEMS`` without changing the recommendation
API: ``select_knowledge`` keeps its signature and ``KnowledgeItem``
keeps its fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeItem:
    """One general training principle (not a user fact)."""

    id: str
    topic: str
    principle: str
    applicability_goals: tuple[str, ...] = ()
    applicability_levels: tuple[str, ...] = ()
    evidence_level: str = "general-principle"
    source: str = "curated"
    limitations: str = ""


KNOWLEDGE_ITEMS: tuple[KnowledgeItem, ...] = (
    KnowledgeItem(
        id="progressive-overload",
        topic="progression",
        principle=(
            "Gradually increasing the demand placed on the body over time "
            "(load, reps, or total work) is the primary driver of continued "
            "strength and muscle adaptation."
        ),
        limitations="Progress cannot increase indefinitely; planned easier periods matter.",
    ),
    KnowledgeItem(
        id="plateau-variation",
        topic="plateau",
        principle=(
            "When performance on a lift is unchanged for many weeks, "
            "changing one training variable at a time (load scheme, rep "
            "range, exercise variant, or weekly frequency for that lift) "
            "is a common way to test whether stagnation resolves."
        ),
        limitations="A flat period can also reflect inconsistent training rather than a true plateau.",
    ),
    KnowledgeItem(
        id="frequency-consistency",
        topic="frequency",
        principle=(
            "Training each major movement or muscle group at least twice "
            "per week is a widely used baseline for steady progress, "
            "provided recovery between sessions is adequate."
        ),
        limitations="Optimal frequency varies with volume, intensity, age, and recovery.",
    ),
    KnowledgeItem(
        id="volume-landmarks-strength",
        topic="volume",
        principle=(
            "For strength-focused training, a small number of heavy, "
            "well-rested sets per lift per week is often sufficient to "
            "drive progress; adding volume is usually considered only "
            "after heavy work stalls."
        ),
        applicability_goals=("strength",),
        limitations="Individual volume needs vary considerably.",
    ),
    KnowledgeItem(
        id="volume-landmarks-hypertrophy",
        topic="volume",
        principle=(
            "For muscle-gain goals, spreading weekly hard sets for a "
            "muscle across two or more sessions is a commonly used "
            "approach to accumulate volume while managing fatigue."
        ),
        applicability_goals=("muscle_gain",),
        limitations="Volume tolerance is individual; more is not always better.",
    ),
    KnowledgeItem(
        id="exercise-selection-compounds",
        topic="exercise-selection",
        principle=(
            "Multi-joint compound movements train more muscle mass per "
            "unit of time and are commonly prioritized as the core of a "
            "session, with isolation work added for specific gaps."
        ),
        limitations="Exercise choice must respect equipment access and injury history.",
    ),
    KnowledgeItem(
        id="balance-push-pull-legs",
        topic="muscle-balance",
        principle=(
            "Covering pushing, pulling, hip-hinge/squat, and carry/core "
            "patterns across the training week is a common check for "
            "balanced full-body development."
        ),
        limitations="Balance is judged over weeks, not single sessions.",
    ),
    KnowledgeItem(
        id="neglected-muscle-rotation",
        topic="muscle-balance",
        principle=(
            "Muscles with little or no mapped training volume over a long "
            "period are often addressed by rotating in one exercise for "
            "that area rather than overhauling the whole program."
        ),
        limitations="Absence from the log may mean untracked rather than untrained work.",
    ),
    KnowledgeItem(
        id="consistency-first-fat-loss",
        topic="consistency",
        principle=(
            "For fat-loss goals supported by training, maintaining regular "
            "resistance sessions matters more than occasional very hard "
            "sessions, because consistency preserves training volume and "
            "habit adherence."
        ),
        applicability_goals=("fat_loss",),
        limitations="Training alone does not determine body-composition outcomes.",
    ),
    KnowledgeItem(
        id="beginner-foundations",
        topic="experience",
        principle=(
            "Less experienced lifters generally progress well by practicing "
            "a small set of core lifts with gradual load increases and "
            "consistent technique, rather than by frequent program changes."
        ),
        applicability_levels=("Beginner",),
        limitations="Training age differs from data-history length in edge cases.",
    ),
    KnowledgeItem(
        id="advanced-specificity",
        topic="experience",
        principle=(
            "Very experienced lifters often need more specific, patient "
            "programming for weak lifts, since easy early gains no longer "
            "apply and progress is measured over months."
        ),
        applicability_levels=("Advanced",),
        limitations="Specificity must still be balanced against overall workload.",
    ),
    KnowledgeItem(
        id="recovery-caution",
        topic="recovery",
        principle=(
            "Persistent pain, sharp pain, or pain that worsens across "
            "sessions is a signal to stop the aggravating activity and "
            "seek qualified professional evaluation rather than pushing "
            "through it."
        ),
        limitations="This is general caution, not medical advice or diagnosis.",
    ),
    KnowledgeItem(
        id="general-fitness-variety",
        topic="variety",
        principle=(
            "For general fitness, rotating across a modest variety of "
            "exercises and movement patterns across the week supports "
            "broad capability and long-term adherence."
        ),
        applicability_goals=("general_fitness",),
        limitations="Variety should not come at the cost of consistency.",
    ),
)


@dataclass
class UserSignals:
    """Deterministic, read-only signals derived from built context."""

    goal: str = "general_fitness"
    level: str = "Beginner"
    has_plateau: bool = False
    low_frequency: bool = False


def select_knowledge(
    signals: UserSignals, limit: int = 6
) -> list[KnowledgeItem]:
    """Select relevant principles for the user's situation.

    Scoring is deterministic: +2 for a matching goal tag, +2 for a
    matching level tag, +2 when the item's topic matches an observed
    signal (plateau/low frequency). Untagged items match everyone.
    Stable order breaks ties by item id.
    """
    scored: list[tuple[int, str, KnowledgeItem]] = []
    for item in KNOWLEDGE_ITEMS:
        if (
            item.applicability_goals
            and signals.goal not in item.applicability_goals
        ):
            continue
        if (
            item.applicability_levels
            and signals.level not in item.applicability_levels
        ):
            continue
        score = 0
        if item.applicability_goals:
            score += 2
        if item.applicability_levels:
            score += 2
        if item.topic == "plateau" and signals.has_plateau:
            score += 2
        if item.topic == "frequency" and signals.low_frequency:
            score += 2
        scored.append((score, item.id, item))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [item for _, _, item in scored[:limit]]


def format_knowledge(items: list[KnowledgeItem]) -> str:
    """Render selected principles as prompt context (not user facts)."""
    lines = [
        "General training principles (background knowledge only -- "
        "these describe training in general, NOT this user; never cite "
        "them as user facts and never attach fact IDs to them):",
    ]
    for item in items:
        lines.append(
            f"- [{item.id} | {item.topic}] {item.principle} "
            f"Limitation: {item.limitations}"
        )
    return "\n".join(lines)


__all__ = [
    "KnowledgeItem",
    "UserSignals",
    "KNOWLEDGE_ITEMS",
    "select_knowledge",
    "format_knowledge",
]
