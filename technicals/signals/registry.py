#!/usr/bin/env python3
# Auto-discovers signal/indicator providers across subpackages.

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Callable, Dict

from queen.helpers.logger import log

# Packages to search (add indicators here too if you want shared registry)
SEARCH_PACKAGES = [
    "queen.technicals.signals.fusion",
    "queen.technicals.signals.tactical",
    "queen.technicals.indicators",  # allow pure indicators to register
]

# Key -> callable (class or function)
_REGISTRY: Dict[str, Callable[..., Any]] = {}


def _canonical(name: str) -> str:
    return name.replace("_", "").replace("-", "").lower()


def _register(name: str, obj: Any):
    key = _canonical(name)
    if key in _REGISTRY:
        # Prefer explicit class/def names over duplicates
        log.warning(f"[Registry] Duplicate '{name}' ignored (already registered).")
        return
    _REGISTRY[key] = obj


def _scan_module(mod):
    # Heuristics:
    # - class with method .evaluate(df) (preferred)
    # - function named compute(df) or evaluate(df)
    for name, obj in inspect.getmembers(mod):
        if inspect.isclass(obj):
            if hasattr(obj, "evaluate") and callable(obj.evaluate):
                _register(name, obj)
        elif inspect.isfunction(obj):
            if (
                name in {"compute", "evaluate"}
                and len(inspect.signature(obj).parameters) == 1
            ):
                # single-arg (df) function
                _register(mod.__name__.split(".")[-1], obj)


def build_registry() -> Dict[str, Callable[..., Any]]:
    if _REGISTRY:
        return _REGISTRY
    for pkg_name in SEARCH_PACKAGES:
        try:
            pkg = importlib.import_module(pkg_name)
        except Exception as e:
            log.warning(f"[Registry] Failed to import package {pkg_name}: {e}")
            continue

        if not hasattr(pkg, "__path__"):
            # Plain module
            _scan_module(pkg)
            continue

        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            try:
                mod = importlib.import_module(m.name)
                _scan_module(mod)
            except Exception as e:
                log.warning(f"[Registry] Import failed {m.name}: {e}")

    log.info(f"[Registry] Built with {len(_REGISTRY)} entries.")
    return _REGISTRY


def get(name: str) -> Callable[..., Any] | None:
    return build_registry().get(_canonical(name))


def names() -> list[str]:
    return sorted(build_registry().keys())
