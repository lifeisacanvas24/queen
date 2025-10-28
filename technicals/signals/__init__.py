#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/__init__.py — package marker
# ============================================================

"""Signals (tactical/pattern/meta) package.

Notes:
- The registry auto-scans this package (and its submodules) with
  pkgutil.walk_packages.
- Keep signal modules here (e.g., tactical/* or simple signal files).
- Expose via EXPORTS, NAME/compute, or compute_<name>() like indicators.

"""

__all__: list[str] = []

from . import fusion, tactical, templates  # noqa: F401

__all__ = ["fusion", "tactical", "templates"]
