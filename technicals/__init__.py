#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/__init__.py — package marker
# ============================================================

"""Indicators package.

Notes:
- The registry auto-scans this package (and its submodules) with
  pkgutil.walk_packages, so we intentionally avoid importing modules here.
- Put indicator modules under this folder (e.g., overlays.py, rsi.py, macd.py).
- Each module may expose:
    • EXPORTS = {"name": callable, ...}      # preferred
      or
    • NAME = "friendly_name"; def compute(...): ...
      or
    • def compute_<name>(df, **kwargs): ...

"""

__all__: list[str] = []

# Re-export registry helpers
from .registry import (
    build_registry,
    get_indicator,
    get_signal,
    list_indicators,
    list_signals,
)

__all__ = [
    "build_registry",
    "list_indicators",
    "list_signals",
    "get_indicator",
    "get_signal",
]
