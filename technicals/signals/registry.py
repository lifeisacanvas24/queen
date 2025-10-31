#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/registry.py
# ------------------------------------------------------------
# Auto-discovers signal/indicator providers across subpackages.
# Priority:
#   1) Module-level EXPORTS dict  (name -> callable/class)
#   2) Classes exposing .evaluate(self, df, **kwargs)
#   3) Functions named compute_*/evaluate/compute with df as first param
# Env:
#   QUEEN_REGISTRY_PACKAGES="pkgA,pkgB,..." to override/extend search roots
# ============================================================
from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
from typing import Any, Callable, Dict, List, Tuple

from queen.helpers.logger import log  # <- use shared logger instance

# Default packages to search (can be extended via env)
_DEFAULT_PACKAGES = [
    "queen.technicals.signals.fusion",
    "queen.technicals.signals.tactical",
    "queen.technicals.indicators",
    "queen.technicals.patterns",
]

# Key -> (callable, module_name)
_REGISTRY: Dict[str, Tuple[Callable[..., Any], str]] = {}


def _search_packages() -> List[str]:
    env = os.getenv("QUEEN_REGISTRY_PACKAGES", "").strip()
    if not env:
        return _DEFAULT_PACKAGES[:]
    # allow either override or extend: ":+pkgX" means extend; otherwise override
    if env.startswith(":+"):
        extra = [p.strip() for p in env[2:].split(",") if p.strip()]
        return _DEFAULT_PACKAGES + extra
    return [p.strip() for p in env.split(",") if p.strip()]


def _canonical(name: str) -> str:
    return name.replace("_", "").replace("-", "").lower()


def _register(name: str, obj: Any, module_name: str):
    key = _canonical(name)
    if key in _REGISTRY:
        # keep first registration to avoid noisy overrides
        log.debug(f"[Registry] Duplicate '{name}' ignored (already registered).")
        return
    _REGISTRY[key] = (obj, module_name)


def _scan_module(mod):
    mod_name = getattr(mod, "__name__", "<?>")

    # 1) Preferred: EXPORTS dict
    exports = getattr(mod, "EXPORTS", None)
    if isinstance(exports, dict):
        for name, obj in exports.items():
            _register(name, obj, mod_name)

    # 2) Classes with .evaluate(self, df, **kwargs)
    for name, obj in inspect.getmembers(mod, inspect.isclass):
        if getattr(obj, "__module__", "") != mod_name:
            continue
        meth = getattr(obj, "evaluate", None)
        if callable(meth):
            sig = inspect.signature(meth)
            params = list(sig.parameters.values())
            if params and params[0].name in {"self", "cls"}:
                _register(name, obj, mod_name)

    # 3) Functions: compute_* / evaluate / compute(df, ...)
    for name, func in inspect.getmembers(mod, inspect.isfunction):
        if getattr(func, "__module__", "") != mod_name:
            continue
        if name.startswith("compute_") or name in {"compute", "evaluate"}:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())
            if not params:
                continue
            first = params[0]
            if first.kind in (first.POSITIONAL_ONLY, first.POSITIONAL_OR_KEYWORD):
                _register(name, func, mod_name)


def build_registry() -> Dict[str, Callable[..., Any]]:
    if _REGISTRY:
        # return names->callables view
        return {k: v[0] for k, v in _REGISTRY.items()}

    for pkg_name in _search_packages():
        try:
            pkg = importlib.import_module(pkg_name)
        except Exception as e:
            log.debug(f"[Registry] Skip package {pkg_name}: {e}")
            continue

        # Plain module
        if not hasattr(pkg, "__path__"):
            _scan_module(pkg)
            continue

        # Walk submodules
        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            try:
                mod = importlib.import_module(m.name)
                _scan_module(mod)
            except Exception as e:
                log.debug(f"[Registry] Import failed {m.name}: {e}")

    log.info(f"[Registry] Built with {len(_REGISTRY)} entries.")
    return {k: v[0] for k, v in _REGISTRY.items()}


def get(name: str) -> Callable[..., Any] | None:
    return build_registry().get(_canonical(name))


def names() -> list[str]:
    return sorted(build_registry().keys())


def names_with_modules() -> List[Tuple[str, str]]:
    """Return [(canonical_name, module_name)] for CLI/debug."""
    build_registry()  # ensure populated
    return sorted(((k, v[1]) for k, v in _REGISTRY.items()), key=lambda x: x[0])


def reset_registry() -> None:
    """Testing helper: clear cache so discovery runs fresh."""
    _REGISTRY.clear()
