#!/usr/bin/env python3
# ============================================================
# queen/helpers/path_manager.py — v1.0
# Thin, forward-only wrapper around SETTINGS.PATHS
# ============================================================
from __future__ import annotations

from pathlib import Path

from queen.helpers.io import ensure_dir
from queen.settings import settings as SETTINGS


def repo_root() -> Path:
    """Best-effort repository root.

    Prefer PATHS['ROOT'] if present, else infer from this file location.
    """
    paths = getattr(SETTINGS, "PATHS", {})
    root = paths.get("ROOT")
    if root:
        return Path(root).expanduser().resolve()
    # Fallback: queen/…/helpers/path_manager.py → repo root ~ two levels up
    return Path(__file__).resolve().parents[2]


def static_dir() -> Path:
    """Return STATIC directory (JSON instruments, holidays, etc.)."""
    return Path(SETTINGS.PATHS["STATIC"]).expanduser().resolve()


def runtime_dir() -> Path:
    """Return RUNTIME directory (cache, logs, runtime data)."""
    p = SETTINGS.PATHS.get("RUNTIME")
    if p:
        return Path(p).expanduser().resolve()
    # harmless fallback near repo root
    return repo_root() / "queen" / "data" / "runtime"


def universe_dir() -> Path:
    """Return UNIVERSE directory (nse_universe.csv, bse_universe.csv, active_universe.csv)."""
    return Path(SETTINGS.PATHS["UNIVERSE"]).expanduser().resolve()


def log_dir() -> Path:
    """Return LOGS directory (core_activity.log etc.)."""
    p = SETTINGS.PATHS.get("LOGS")
    if p:
        return Path(p).expanduser().resolve()
    return runtime_dir() / "logs"


def positions_dir() -> Path:
    """Return directory where *_positions.json live."""
    # You mentioned:
    #   queen/data/static/positions/*_positions.json
    base = static_dir() / "positions"
    ensure_dir(base / "dummy")  # ensures directory exists, no file created
    return base


def position_file(stem: str) -> Path:
    """Return path to a specific positions file, e.g. 'ank' → ank_positions.json."""
    base = positions_dir()
    filename = f"{stem}_positions.json"
    return (base / filename).expanduser().resolve()


__all__ = [
    "repo_root",
    "static_dir",
    "runtime_dir",
    "universe_dir",
    "log_dir",
    "positions_dir",
    "position_file",
]
