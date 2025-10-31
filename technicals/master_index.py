#!/usr/bin/env python3
# ============================================================
# queen/technicals/master_index.py — Master index (indicators / signals / patterns)
# DRY: reuses the central registry scanner
# ============================================================
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Iterable, Tuple

import polars as pl
from queen.technicals import registry


def _scan_package(pkg: str) -> Iterable[Tuple[str, str]]:
    """Generic scan: yields (name, module) by looking for:
    • EXPORTS dict
    • compute_* callables
    • NAME + compute()
    """
    try:
        package = importlib.import_module(pkg)
    except Exception:
        return []

    if not hasattr(package, "__path__"):
        return []

    found: list[Tuple[str, str]] = []
    for info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        try:
            mod = importlib.import_module(info.name)
        except Exception:
            continue

        # 1) explicit EXPORTS
        exports = getattr(mod, "EXPORTS", None)
        if isinstance(exports, dict):
            for k, v in exports.items():
                if callable(v):
                    found.append((k, mod.__name__))

        # 2) NAME + compute()
        name = getattr(mod, "NAME", None)
        comp = getattr(mod, "compute", None)
        if isinstance(name, str) and callable(comp):
            found.append((name, mod.__name__))

        # 3) compute_* functions
        for n, v in inspect.getmembers(mod, inspect.isfunction):
            if n.startswith("compute_"):
                key = n.replace("compute_", "", 1)
                found.append((key, mod.__name__))
    return found


def master_index() -> pl.DataFrame:
    """Return a master DataFrame with kind/name/module for:
    - indicators (registry)
    - signals (registry)
    - patterns  (explicit scan of queen.technicals.patterns.*)
    """
    # registry-backed indicators/signals
    registry.build_registry()
    indicators = [
        ("indicator", n, registry._REG_INDICATORS[n].fn.__module__)  # type: ignore[attr-defined]
        for n in registry.list_indicators()
    ]
    signals = [
        ("signal", n, registry._REG_SIGNALS[n].fn.__module__)  # type: ignore[attr-defined]
        for n in registry.list_signals()
    ]

    # explicit pattern scan (keeps future-proof if patterns move)
    patterns_raw = list(_scan_package("queen.technicals.patterns"))
    patterns = [("pattern", name, mod) for (name, mod) in patterns_raw]

    # combine + normalize names (canonical, lower_snake)
    items = []
    for kind, name, mod in indicators + signals + patterns:
        items.append((kind, name.strip().lower().replace(" ", "_"), mod))

    return pl.DataFrame(items, schema=["kind", "name", "module"], orient="row").sort(
        by=["kind", "name"]
    )
