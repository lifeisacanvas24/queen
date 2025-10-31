# queen/helpers/common.py  (slim, no settings or polars)
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def logger_supports_color(logger: logging.Logger) -> bool:
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
    if enabled and color_key in palette:
        return f"{palette.get(color_key,'')}{text}{palette.get('reset','')}"
    return text


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
    tf = (tf or "").strip().lower()
    if not tf:
        return "intraday_5m"
    if tf in _ALIASES:
        return _ALIASES[tf]
    if tf.endswith("m"):
        return f"intraday_{tf}"
    if tf.endswith("h"):
        return f"hourly_{tf}"
    return f"intraday_{tf}"


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
    if not params:
        return {}
    meta = _META_INDICATOR_KEYS if deny is None else (_META_INDICATOR_KEYS | set(deny))
    return {k: v for k, v in params.items() if k not in meta}
