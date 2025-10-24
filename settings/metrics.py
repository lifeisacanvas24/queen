#!/usr/bin/env python3
# ============================================================
# queen/settings/metrics.py — Market Metrics Configuration (v8.0)
# ============================================================
"""Metric Toggles and Thresholds for Market Snapshots
---------------------------------------------------
📊 Purpose:
    Controls runtime-enabled metrics, thresholds, and formatting
    for analytics modules (e.g., cockpit, summary dashboards).

💡 Usage:
    from queen.settings import metrics
    if "volatility_index" in metrics.ENABLED:
        ...
"""

from __future__ import annotations

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
# 🧠 Summary Helper
# ------------------------------------------------------------
def summary() -> dict:
    """Return merged view for introspection or CLI use."""
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
