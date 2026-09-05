"""Collect and mask process environment variables for LLM context."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Mapping

DEFAULT_ENV_KEYS: tuple[str, ...] = (
    "NLP2DSL_BACKEND_URL",
    "NLP2DSL_NLP_SERVICE_URL",
    "NLP2DSL_WORKER_URL",
    "NLP2DSL_TIMEOUT",
    "NLP_ENRICH_MISSING",
    "NLP2DSL_UTF8",
    "NLP_CHAT_MODE",
    "LLM_MODEL",
    "OPENROUTER_API_KEY",
    "LLM_API_BASE",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "NLP2CMD_INTEGRATION",
    "NLP2CMD_INTRACT_GATE",
    "ENV2LLM_PROJECT_DIR",
)


def mask_secret(value: str) -> str:
    if not value or len(value) < 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _is_secret_key(key: str) -> bool:
    return any(token in key for token in ("KEY", "SECRET", "TOKEN", "PASSWORD"))


def _env_value(key: str, raw: str) -> str:
    return mask_secret(raw) if _is_secret_key(key) else raw


def _collect_default_keys(
    out: dict[str, str],
    keys: tuple[str, ...],
) -> None:
    for key in keys:
        raw = os.environ.get(key)
        if raw is None:
            continue
        out[key] = _env_value(key, raw)


def _collect_prefixed_keys(
    out: dict[str, str],
    *,
    include_all_prefixes: tuple[str, ...],
) -> None:
    for key, raw in sorted(os.environ.items()):
        if key in out or raw is None:
            continue
        if not any(key.startswith(prefix) for prefix in include_all_prefixes):
            continue
        out[key] = _env_value(key, raw)


def collect_environment(
    *,
    extra_keys: tuple[str, ...] = (),
    include_all_prefixes: tuple[str, ...] = ("NLP2DSL_", "LLM_", "OPENROUTER_", "ENV2LLM_"),
) -> dict[str, str]:
    """Snapshot relevant env vars (secrets masked) for environment blocks."""
    keys = tuple(dict.fromkeys((*DEFAULT_ENV_KEYS, *extra_keys)))
    out: dict[str, str] = {}
    _collect_default_keys(out, keys)
    if include_all_prefixes:
        _collect_prefixed_keys(out, include_all_prefixes=include_all_prefixes)
    out["generated_at"] = datetime.now(timezone.utc).isoformat()
    return out


def merge_environment(
    base: Mapping[str, str] | None,
    override: Mapping[str, str] | None,
) -> dict[str, str]:
    merged = dict(base or {})
    merged.update(dict(override or {}))
    return merged
