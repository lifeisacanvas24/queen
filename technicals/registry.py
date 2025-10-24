#!/usr/bin/env python3
# ============================================================
# queen/technicals/registry.py — v1.0 (Indicators & Signals)
# ============================================================
from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Callable, Dict

import polars as pl


@dataclass(frozen=True)
class Entry:
    name: str
    fn: Callable[[pl.DataFrame], pl.DataFrame | pl.Series | dict]


_REG_INDICATORS: Dict[str, Entry] = {}
_REG_SIGNALS: Dict[str, Entry] = {}


# ---------- helpers ----------
def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _register_many(target: Dict[str, Entry], exports: Dict[str, Callable]):
    for k, v in exports.items():
        key = _norm(k)
        if callable(v):
            target[key] = Entry(name=key, fn=v)


def _try_module_exports(mod, target: Dict[str, Entry]) -> int:
    """Return number of items registered for this module."""
    count = 0
    # 1) explicit EXPORTS dict
    exports = getattr(mod, "EXPORTS", None)
    if isinstance(exports, dict):
        _register_many(target, exports)
        count += len(exports)

    # 2) NAME + compute()
    name = getattr(mod, "NAME", None)
    comp = getattr(mod, "compute", None)
    if isinstance(name, str) and callable(comp):
        key = _norm(name)
        target[key] = Entry(name=key, fn=comp)
        count += 1

    # 3) any compute_* functions
    for n, v in inspect.getmembers(mod, inspect.isfunction):
        if n.startswith("compute_"):
            key = _norm(n.replace("compute_", "", 1))
            target[key] = Entry(name=key, fn=v)
            count += 1
    return count


def _autoscan(pkg: str, target: Dict[str, Entry]) -> int:
    """Scan a package for modules and register exports by convention."""
    found = 0
    try:
        package = importlib.import_module(pkg)
    except Exception:
        return 0
    if not hasattr(package, "__path__"):
        return 0
    for info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        try:
            mod = importlib.import_module(info.name)
            found += _try_module_exports(mod, target)
        except Exception:
            # keep scanning; bad modules won’t break registry
            continue
    return found


# ---------- public API ----------
def build_registry(force: bool = False) -> None:
    """Idempotent build for indicators & signals."""
    if _REG_INDICATORS and _REG_SIGNALS and not force:
        return
    _REG_INDICATORS.clear()
    _REG_SIGNALS.clear()
    _autoscan("queen.technicals.indicators", _REG_INDICATORS)
    _autoscan("queen.technicals.signals", _REG_SIGNALS)


def list_indicators() -> list[str]:
    if not _REG_INDICATORS:
        build_registry()
    return sorted(_REG_INDICATORS.keys())


def list_signals() -> list[str]:
    if not _REG_SIGNALS:
        build_registry()
    return sorted(_REG_SIGNALS.keys())


def get_indicator(name: str) -> Callable:
    if not _REG_INDICATORS:
        build_registry()
    key = _norm(name)
    if key not in _REG_INDICATORS:
        raise KeyError(f"Indicator not found: {name}")
    return _REG_INDICATORS[key].fn


def get_signal(name: str) -> Callable:
    if not _REG_SIGNALS:
        build_registry()
    key = _norm(name)
    if key not in _REG_SIGNALS:
        raise KeyError(f"Signal not found: {name}")
    return _REG_SIGNALS[key].fn
