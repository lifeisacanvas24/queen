#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_patterns_utils.py
# ------------------------------------------------------------
# ✅ Sanity tests for queen/technicals/signals/utils_patterns.py
# Verifies label generation, family grouping, and deterministic picking
# ============================================================
from __future__ import annotations

import importlib
import random
import sys
import types
from pathlib import Path

# -----------------------------------------------------------------------------
# Setup import path
# -----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# -----------------------------------------------------------------------------
# Mock patterns registry
# -----------------------------------------------------------------------------
MOCK_PATTERNS = {
    "japanese": {
        "hammer": {"contexts": {"intraday_15m": {}, "daily": {}}},
        "shooting_star": {"contexts": {"intraday_15m": {}}},
    },
    "composite": {
        "morning_star": {"contexts": {"daily": {}, "weekly": {}}},
        "evening_star": {"contexts": {"daily": {}}},
    },
}

# -----------------------------------------------------------------------------
# Patch module import before reloading utils_patterns
# -----------------------------------------------------------------------------
mock_settings = types.ModuleType("queen.settings.patterns")
mock_settings.PATTERNS = MOCK_PATTERNS
sys.modules["queen.settings.patterns"] = mock_settings

# Reload utils_patterns to use the mock data
utils_patterns = importlib.import_module("queen.technicals.signals.utils_patterns")
importlib.reload(utils_patterns)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
def test_get_patterns_for_timeframe():
    items = utils_patterns.get_patterns_for_timeframe("daily")
    assert any("Morning Star" in lbl for lbl, _ in items)
    assert any("Hammer" in lbl for lbl, _ in items)
    assert all(isinstance(lbl, str) and isinstance(icon, str) for lbl, icon in items)
    print("✅ get_patterns_for_timeframe passed")


def test_random_and_deterministic_labels():
    tf = "intraday_15m"
    label1 = utils_patterns.get_random_pattern_label(tf)
    label2 = utils_patterns.get_deterministic_pattern_label(tf, 1)
    assert isinstance(label1, str) and isinstance(label2, str)
    assert "🕯️" in label1 or "🧩" in label1
    print(f"✅ random/deterministic labels → {label1}, {label2}")


def test_grouped_by_family():
    grouped = utils_patterns.get_patterns_grouped_by_family("daily")
    assert "japanese" in grouped and "composite" in grouped
    assert any("Hammer" in lbl for lbl, _ in grouped["japanese"])
    print("✅ get_patterns_grouped_by_family passed")


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    random.seed(42)
    test_get_patterns_for_timeframe()
    test_random_and_deterministic_labels()
    test_grouped_by_family()
    print("✅ smoke_patterns_utils: all checks passed")
