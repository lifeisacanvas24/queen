# queen/helpers/common.py
# v1.0 — tiny shared helpers (no settings imports)

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
    """Wrap `text` with ANSI codes from `palette` (e.g., DEFAULTS.CONSOLE_COLORS)
    when enabled. `palette` should contain keys like 'cyan', 'yellow', 'green', 'red', 'reset'.
    """
    if enabled and color_key in palette:
        return f"{palette.get(color_key,'')}{text}{palette.get('reset','')}"
    return text


# ---- timeframe token normalizer ----
def timeframe_key(tf: str) -> str:
    """Map raw tokens to context keys used by settings (patterns policy):
    '5m' -> 'intraday_5m', '1h' -> 'hourly_1h', '1d' -> 'daily', '1w' -> 'weekly', '1mo' -> 'monthly'
    """
    tf = (tf or "").lower()
    if tf.endswith("m"):
        return f"intraday_{tf}"
    if tf.endswith("h"):
        return f"hourly_{tf}"
    if tf == "1d":
        return "daily"
    if tf == "1w":
        return "weekly"
    if tf == "1mo":
        return "monthly"
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


def indicator_kwargs(params: Dict[str, Any] | None) -> Dict[str, Any]:
    """Keep only indicator-native kwargs (e.g., length=14) and drop policy/meta knobs.
    Safe to pass directly into indicator functions.
    """
    if not params:
        return {}
    return {k: v for k, v in params.items() if k not in _META_INDICATOR_KEYS}
