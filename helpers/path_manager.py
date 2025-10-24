#!/usr/bin/env python3
# ============================================================
# quant/utils/path_manager.py — Config-Driven Path Resolver (v8.1 Hybrid-Safe)
# ============================================================
"""Quant-Core centralized path resolver with config-proxy integration.

Highlights:
    ✅ Uses config_proxy (no direct config import → circular-safe)
    ✅ Unified access to runtime/log/export/cache dirs
    ✅ Smart key normalization for legacy aliases (logs_dir → logs)
    ✅ Built-in log rotation & safety fallbacks
    ✅ Works even before config bootstrap (self-healing)
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

# 🔒 Circular-safe config access
from quant.utils.config_proxy import cfg_get, cfg_path
from quant.utils.logs import safe_log_init

# ------------------------------------------------------------
# 🧭 Setup
# ------------------------------------------------------------
logger = safe_log_init("PathManager")

# ------------------------------------------------------------
# 🧠 Smart Path Key Mapper
# ------------------------------------------------------------
_KEY_MAP = {
    "logs_dir": "logs",
    "cache_dir": "cache",
    "exports_dir": "exports",
    "profiles_dir": "profiles",
    "root_dir": "root",
}


# ============================================================
# 🧩 Core Directory Utilities
# ============================================================
def _ensure_dir(p: Path) -> Path:
    """Ensure directory exists (mkdir -p) and return resolved path."""
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def _get_path_from_config(key: str, default: Optional[str] = None) -> Path:
    """Wrapper around cfg_path() with alias resolution and graceful fallback."""
    normalized = _KEY_MAP.get(key.replace("paths.", ""), key.replace("paths.", ""))
    try:
        path = cfg_path(f"paths.{normalized}", default or ".")
        return _ensure_dir(path)
    except Exception as e:
        logger.warning(f"[PathResolveFallback] {normalized} → {e}")
        path = Path(default or ".").resolve()
        return _ensure_dir(path)


# ============================================================
# 🗂️ Root Directories
# ============================================================
def get_root_dir() -> Path:
    return _get_path_from_config("root", "./quant")


def get_logs_dir() -> Path:
    return _get_path_from_config("logs", "./data/runtime/logs")


def get_cache_dir() -> Path:
    return _get_path_from_config("cache", "./data/runtime/cache")


def get_exports_dir() -> Path:
    return _get_path_from_config("exports", "./data/runtime/exports")


def get_profiles_dir() -> Path:
    return _get_path_from_config("profiles", "./data/static/profiles")


def get_indicator_health_log() -> Path:
    """Return path to indicator health log file."""
    return _get_path_from_config(
        "indicator_health_log", "./data/runtime/logs/indicator_health_log.csv"
    )


# ============================================================
# 🧩 Dev Diagnostic Snapshot Helpers
# ============================================================
def get_dev_logs_dir() -> Path:
    """Return development logs directory."""
    return _get_path_from_config("dev_logs_dir", "./logs/dev")


def get_dev_snapshot_path(key: str) -> Path:
    """Return path for a dev diagnostic snapshot (breadth_momentum, macd, etc.)."""
    dev_snapshots = cfg_get("dev_test_snapshots", {})
    filename = dev_snapshots.get(key, f"{key}_test.json")
    return get_dev_logs_dir() / filename


# ============================================================
# 🧠 Log Rotation Helpers
# ============================================================
def _rotate_log_file_if_needed(path: Path) -> None:
    """Perform size-based rotation if enabled via config.logging settings."""
    log_cfg = cfg_get("logging", {}) or {}
    rotate_enabled = log_cfg.get("rotate_enabled", True)
    max_size_mb = int(log_cfg.get("max_size_mb", 5))
    backup_count = int(log_cfg.get("backup_count", 5))

    if not rotate_enabled or not path.exists() or not path.is_file():
        return

    max_bytes = max_size_mb * 1024 * 1024
    if path.stat().st_size < max_bytes:
        return

    try:
        # Rotate existing backups backwards
        for i in range(backup_count - 1, 0, -1):
            src = path.with_suffix(f".log.{i}")
            dst = path.with_suffix(f".log.{i + 1}")
            if src.exists():
                shutil.move(str(src), str(dst))

        rotated = path.with_suffix(".log.1")
        shutil.move(str(path), str(rotated))
        path.touch()
        logger.info(
            f"[ROTATE] {path.name} exceeded {max_size_mb}MB (max backups={backup_count})"
        )
    except Exception as e:
        logger.warning(f"[ROTATE_FAIL] {path}: {e}")


def get_rotated_indicator_health_log() -> Path:
    """Get indicator health log path, rotating it if needed."""
    path = get_indicator_health_log()
    _rotate_log_file_if_needed(path)
    return path


# ============================================================
# 🧭 Path Summary (for cockpit/diagnostics)
# ============================================================
def summary() -> dict[str, str]:
    """Return all primary data directories (for debugging)."""
    return {
        "root": str(get_root_dir()),
        "logs_dir": str(get_logs_dir()),
        "cache_dir": str(get_cache_dir()),
        "exports_dir": str(get_exports_dir()),
        "profiles_dir": str(get_profiles_dir()),
        "indicator_health_log": str(get_indicator_health_log()),
    }


# ============================================================
# 🧪 CLI Self-Test
# ============================================================
if __name__ == "__main__":
    print("📁 Root Dir:", get_root_dir())
    print("📦 Logs Dir:", get_logs_dir())
    print("🧩 Dev Snapshot:", get_dev_snapshot_path("breadth_momentum"))
    print("📊 Indicator Health Log →", get_rotated_indicator_health_log())
