# queen/helpers/common.py
# v1.1 — tiny shared helpers (no settings or polars imports)

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


# ---- time ----
def utc_now_iso() -> str:
    """UTC timestamp like 2025-10-27T06:41:12.323113Z."""
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


# ---- terminal color support ----
def logger_supports_color(logger: logging.Logger) -> bool:
    """True iff output stream is a TTY and NO_COLOR is not set."""
    if os.environ.get("NO_COLOR"):
        return False
    for h in logger.handlers:
        stream = getattr(h, "stream", None)
        try:
            if stream and hasattr(stream, "isatty") and stream.isatty():
                return True
        except Exception:
            pass
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def colorize(text: str, color_key: str, palette: Dict[str, str], enabled: bool) -> str:
    """Wrap `text` with ANSI codes from `palette` (expects keys: 'cyan','yellow','green','red','reset')."""
    if enabled and color_key in palette:
        return f"{palette.get(color_key,'')}{text}{palette.get('reset','')}"
    return text


def log_file(name: str) -> Path:
    """Return resolved path for a named log stream (e.g., 'CORE')."""
    files = (LOGGING or {}).get("FILES", {})
    fname = files.get(name.upper(), f"{name.lower()}.log")
    return Path(PATHS["LOGS"]) / fname


# ---- timeframe token normalizer ----
_ALIASES = {
    "d": "daily",
    "day": "daily",
    "daily": "daily",
    "1d": "daily",
    "w": "weekly",
    "week": "weekly",
    "weekly": "weekly",
    "1w": "weekly",
    "mo": "monthly",
    "mon": "monthly",
    "month": "monthly",
    "monthly": "monthly",
    "1mo": "monthly",
}


def timeframe_key(tf: str) -> str:
    """Map raw tokens to settings/policy context keys:
    '5m' → 'intraday_5m', '1h' → 'hourly_1h', aliases: 'daily'/'1d' → 'daily', etc.
    """
    tf = (tf or "").strip().lower()
    if not tf:
        return "intraday_5m"
    if tf in _ALIASES:
        return _ALIASES[tf]
    if tf.endswith("m"):
        return f"intraday_{tf}"
    if tf.endswith("h"):
        return f"hourly_{tf}"
    # fall back to intraday token if unknown
    return f"intraday_{tf}"


# ---- indicator kwargs filter ----
_META_INDICATOR_KEYS = {
    "min_bars",
    "need",
    "lookback",
    "context",
    "context_key",
    "timeframe",
    "tf",
}


def indicator_kwargs(
    params: Dict[str, Any] | None, *, deny: set[str] | None = None
) -> Dict[str, Any]:
    """Keep only indicator-native kwargs (e.g., length=14); drop policy/meta knobs."""
    if not params:
        return {}
    meta = _META_INDICATOR_KEYS if deny is None else (_META_INDICATOR_KEYS | set(deny))
    return {k: v for k, v in params.items() if k not in meta}
