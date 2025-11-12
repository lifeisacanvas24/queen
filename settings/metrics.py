#!/usr/bin/env python3
# ============================================================
# queen/settings/metrics.py — Market Metrics Configuration (v9.0)
# Forward-only, DRY, tiny helpers + validator
# ============================================================
from __future__ import annotations

from typing import Iterable

__all__ = ["ENABLED", "THRESHOLDS", "FORMATTING", "is_enabled", "enable", "validate", "summary"]

# ------------------------------------------------------------
# 🧩 Core Metric Toggles
# ------------------------------------------------------------
ENABLED: list[str] = [
    "market_summary",
    "avg_close",
    "total_volume",
    "avg_change_pct",
    "volatility_index",
    "breadth_ratio",
    "sector_heatmap",
]

# ------------------------------------------------------------
# 📏 Threshold Configuration
# ------------------------------------------------------------
THRESHOLDS: dict[str, float | int] = {
    "min_symbol_count": 3,
    "volume_alert_threshold": 1_000_000,
}

# ------------------------------------------------------------
# 🧮 Formatting Rules
# ------------------------------------------------------------
FORMATTING: dict[str, str | int] = {
    "rounding_precision": 2,
    "timestamp_format": "%Y-%m-%dT%H:%M:%S",
}

# ------------------------------------------------------------
# 🧠 Helpers
# ------------------------------------------------------------
def is_enabled(name: str) -> bool:
    return (name or "").strip().lower() in (m.lower() for m in ENABLED)

def enable(names: Iterable[str]) -> None:
    """Forward-only convenience: extend ENABLED with unique names."""
    seen = {m.lower() for m in ENABLED}
    for n in names:
        n = (n or "").strip()
        if n and n.lower() not in seen:
            ENABLED.append(n)
            seen.add(n.lower())

def validate() -> dict:
    errs: list[str] = []
    if not isinstance(ENABLED, list) or not all(isinstance(x, str) and x for x in ENABLED):
        errs.append("ENABLED must be a list[str] with non-empty names")
    if not isinstance(THRESHOLDS, dict):
        errs.append("THRESHOLDS must be dict")
    if not isinstance(FORMATTING, dict):
        errs.append("FORMATTING must be dict")
    if "rounding_precision" in FORMATTING and (
        not isinstance(FORMATTING["rounding_precision"], int) or FORMATTING["rounding_precision"] < 0
    ):
        errs.append("FORMATTING.rounding_precision must be non-negative int")
    return {"ok": len(errs) == 0, "errors": errs, "count": len(ENABLED)}

def summary() -> dict:
    return {
        "enabled_metrics": ENABLED,
        "thresholds": THRESHOLDS,
        "formatting": FORMATTING,
    }

# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🧩 Queen Metrics Settings")
    print(summary())
    print(validate())
