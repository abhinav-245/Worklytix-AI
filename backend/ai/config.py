"""Gemini configuration (Phase 12).

The API key lives server-side only: ``os.environ`` first, then
``backend/.env`` (``GEMINI_API_KEY`` / ``GEMINI_MODEL``). It is never
exposed to the frontend, never logged, and ``backend/.env`` is git-ignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "gemini-2.5-flash"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines (no interpolation, no export keyword)."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and (len(value) < 2 or not value.startswith("$(")):
            values[key] = value.strip("\"'")
    return values


@dataclass(frozen=True)
class GeminiConfig:
    """Resolved Gemini settings; empty api_key means not configured."""

    api_key: str = ""
    model: str = DEFAULT_MODEL

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())


def load_gemini_config(
    env: dict[str, str] | None = None,
    env_file: Path | None = ENV_FILE,
) -> GeminiConfig:
    """Resolve config from process env, falling back to backend/.env.

    Pass ``env_file=None`` to disable file fallback (hermetic tests).
    """
    source = env if env is not None else os.environ
    api_key = (source.get("GEMINI_API_KEY") or "").strip()
    model = (source.get("GEMINI_MODEL") or "").strip() or DEFAULT_MODEL
    if not api_key and env_file is not None:
        file_values = _read_env_file(env_file)
        api_key = (file_values.get("GEMINI_API_KEY") or "").strip()
        if not (source.get("GEMINI_MODEL") or "").strip():
            model = (file_values.get("GEMINI_MODEL") or "").strip() or model
    return GeminiConfig(api_key=api_key, model=model)


__all__ = [
    "DEFAULT_MODEL",
    "GeminiConfig",
    "load_gemini_config",
]
