#!/usr/bin/env python3
# ============================================================
# queen/technicals/registry.py — v1.2 (Auto-discovery, DRY, safe)
# ============================================================
from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import polars as pl


@dataclass(frozen=True)
class Entry:
    name: str
    fn: Callable[..., pl.DataFrame | pl.Series | dict | None]


_REG_INDICATORS: Dict[str, Entry] = {}
_REG_SIGNALS: Dict[str, Entry] = {}


# ---------- helpers ----------
def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _resolve_dotted(root_mod, dotted: str) -> Optional[Callable]:
    """Allow EXPORTS to contain dotted names ('module.func')."""
    try:
        if "." in dotted:
            mod_name, func_name = dotted.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, func_name, None)
            return fn if callable(fn) else None
        return (
            getattr(root_mod, dotted, None)
            if callable(getattr(root_mod, dotted, None))
            else None
        )
    except Exception:
        return None


def _register_many(target: Dict[str, Entry], mod, exports: Dict) -> int:
    count = 0
    for k, v in exports.items():
        key = _norm(k)
        fn = v if callable(v) else _resolve_dotted(mod, str(v))
        if callable(fn):
            target[key] = Entry(name=key, fn=fn)
            count += 1
    return count


def _try_module_exports(mod, target: Dict[str, Entry]) -> int:
    """Return number of items registered for this module."""
    count = 0
    # 1) explicit EXPORTS dict (functions or dotted names)
    exports = getattr(mod, "EXPORTS", None)
    if isinstance(exports, dict):
        count += _register_many(target, mod, exports)

    # 2) NAME + compute()
    name = getattr(mod, "NAME", None)
    comp = getattr(mod, "compute", None)
    if isinstance(name, str) and callable(comp):
        key = _norm(name)
        target[key] = Entry(name=key, fn=comp)
        count += 1

    # 3) any compute_* functions (auto-expose)
    for n, v in inspect.getmembers(mod, inspect.isfunction):
        if n.startswith("compute_"):
            key = _norm(n.replace("compute_", "", 1))
            target[key] = Entry(name=key, fn=v)
            count += 1
    return count


def _autoscan(pkg: str, target: Dict[str, Entry]) -> int:
    """Scan a package for modules and register exports by convention."""
    try:
        package = importlib.import_module(pkg)
    except Exception:
        return 0
    if not hasattr(package, "__path__"):
        return 0

    found = 0
    for info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        # ignore private / test / demo modules during autoscan
        if any(seg.startswith("_") for seg in info.name.split(".")):
            continue
        if ".tests." in info.name or ".scripts." in info.name or ".demo" in info.name:
            continue
        try:
            mod = importlib.import_module(info.name)
            found += _try_module_exports(mod, target)
        except Exception:
            # tolerate bad modules; continue scanning
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


def get_indicator(name: str) -> Callable[..., pl.DataFrame | pl.Series | dict | None]:
    if not _REG_INDICATORS:
        build_registry()
    key = _norm(name)
    if key not in _REG_INDICATORS:
        raise KeyError(f"Indicator not found: {name}")
    return _REG_INDICATORS[key].fn


def get_signal(name: str) -> Callable[..., pl.DataFrame | pl.Series | dict | None]:
    if not _REG_SIGNALS:
        build_registry()
    key = _norm(name)
    if key not in _REG_SIGNALS:
        raise KeyError(f"Signal not found: {name}")
    return _REG_SIGNALS[key].fn


def register_indicator(name: str, fn: Callable) -> None:
    _REG_INDICATORS[_norm(name)] = Entry(name=_norm(name), fn=fn)


def register_signal(name: str, fn: Callable) -> None:
    _REG_SIGNALS[_norm(name)] = Entry(name=_norm(name), fn=fn)
