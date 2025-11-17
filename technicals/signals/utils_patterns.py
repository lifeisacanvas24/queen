#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/utils_patterns.py
# ------------------------------------------------------------
# 🧩 Pattern Utilities — integrates queen.settings.patterns.PATTERNS
# into cockpit / signal layers.
#
# Expects queen.settings.patterns to expose:
#   PATTERNS: Dict[str, Dict[str, Dict]]
#
# Example shape:
# PATTERNS = {
#   "japanese": {
#       "hammer": {
#           "contexts": {"intraday_15m": {...}, "daily": {...}},
#           ...
#       },
#       ...
#   },
#   "cumulative": { ... },
#   ...
# }
#
# ❗ Strict: if PATTERNS is missing or malformed, import will fail.
# ============================================================

from __future__ import annotations

from typing import Dict, List, Tuple

from queen.settings.patterns import PATTERNS as _PATTERNS

FAMILY_ICONS: Dict[str, str] = {
    "japanese": "🕯️",
    "cumulative": "🔁",
    "other": "🧩",
}

__all__ = [
    "get_patterns_for_timeframe",
    "get_deterministic_pattern_label",
    "get_patterns_grouped_by_family",
]


# ----------------------------
# Internal helpers
# ----------------------------
def _catalog() -> Dict[str, Dict[str, Dict]]:
    return _PATTERNS


def _norm_tf(s: str) -> str:
    return (s or "").strip().lower()


def _titleize(name: str) -> str:
    return (name or "").replace("_", " ").title()


# ----------------------------
# Public API
# ----------------------------
def get_patterns_for_timeframe(timeframe: str) -> List[Tuple[str, str]]:
    """Return [(label, family_icon), ...] applicable to a given timeframe key."""
    cat = _catalog()
    tf = _norm_tf(timeframe)
    out: List[Tuple[str, str]] = []

    for family, entries in cat.items():
        if not isinstance(entries, dict):
            continue
        icon = FAMILY_ICONS.get(family, FAMILY_ICONS["other"])
        for name, meta in entries.items():
            if not isinstance(meta, dict):
                continue
            ctx = meta.get("contexts") or {}
            # normalize keys for robust matching
            if any(_norm_tf(k) == tf for k in ctx.keys()):
                out.append((_titleize(name), icon))
    return out


def get_deterministic_pattern_label(timeframe: str, index: int) -> str:
    """Return a deterministic label+icon for a given timeframe and index."""
    items = get_patterns_for_timeframe(timeframe)
    if not items:
        return "—"
    idx = index % len(items)
    label, icon = items[idx]
    return f"{icon} {label}"


def get_patterns_grouped_by_family(timeframe: str) -> Dict[str, List[Tuple[str, str]]]:
    """Return { family_name: [(label, icon), ...] } filtered by timeframe."""
    cat = _catalog()
    tf = _norm_tf(timeframe)
    grouped: Dict[str, List[Tuple[str, str]]] = {}

    for family, entries in cat.items():
        if not isinstance(entries, dict):
            continue
        icon = FAMILY_ICONS.get(family, FAMILY_ICONS["other"])
        bucket: List[Tuple[str, str]] = []
        for name, meta in entries.items():
            if not isinstance(meta, dict):
                continue
            ctx = meta.get("contexts") or {}
            if any(_norm_tf(k) == tf for k in ctx.keys()):
                bucket.append((_titleize(name), icon))
        if bucket:
            grouped[family] = bucket
    return grouped
