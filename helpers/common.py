# queen/helpers/common.py
# v1.2 — tiny shared helpers (no settings imports)

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

import polars as pl


# ---- time ----
def utc_now_iso() -> str:
    """UTC timestamp like 2025-10-27T06:41:12.323113Z."""
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc_expr(expr: pl.Expr) -> pl.Expr:
    """Parse ISO-8601 strings to tz-aware UTC Datetime.
    Supports '...Z' or '...+HH:MM' offsets. Returns pl.Datetime(tz='UTC').
    """
    t_z = expr.str.strptime(
        pl.Datetime, format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC", strict=False
    )
    t_off = expr.str.strptime(
        pl.Datetime, format="%Y-%m-%dT%H:%M:%S%.f%z", strict=False
    ).dt.convert_time_zone("UTC")
    return pl.coalesce([t_z, t_off])


# ---- timeframe token normalizer (single owner) ----
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
    """Map raw tokens to settings/policy context keys.
    '5m'→'intraday_5m', '1h'→'hourly_1h', aliases map to daily/weekly/monthly.
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
    params: Dict[str, Any] | None, *, deny: Iterable[str] | None = None
) -> Dict[str, Any]:
    if not params:
        return {}
    deny_set = set(_META_INDICATOR_KEYS) | (set(deny) if deny else set())
    return {k: v for k, v in params.items() if k not in deny_set}


# ---- terminal color support ----
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
