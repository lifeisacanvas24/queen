#!/usr/bin/env python3
from __future__ import annotations
import sys, types, importlib
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# Create a fake module with EXPORTS to ensure discovery works
fake_mod = types.ModuleType("queen.technicals.signals.tactical._mocksignal")


def _dummy(df, **kwargs):
    return df


fake_mod.EXPORTS = {"mock_signal": _dummy}
sys.modules["queen.technicals.signals.tactical._mocksignal"] = fake_mod

# Ensure the parent package exists in sys.modules
import types as _t

if "queen.technicals.signals.tactical" not in sys.modules:
    sys.modules["queen.technicals.signals.tactical"] = _t.ModuleType(
        "queen.technicals.signals.tactical"
    )

registry = importlib.import_module("queen.technicals.signals.registry")
# Force rebuild each run
registry._REGISTRY.clear()  # type: ignore[attr-defined]
names = registry.names()
assert any("mock" in n for n in names), f"EXPORTS not discovered: {names}"
print("✅ smoke_signals_registry: all checks passed")
