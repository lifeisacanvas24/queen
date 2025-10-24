#!/usr/bin/env python3
# ============================================================
# quant/utils/io.py — Core IO Utilities (v2.5 HYBRID-SAFE FINAL)
# ============================================================
"""Unified I/O helpers for the Quant-Core system.

Highlights:
    ✅ Centralized file loading (JSON, CSV, Parquet)
    ✅ Config-aware data root discovery (no hardcoded paths)
    ✅ Safe atomic writes + checksum integrity
    ✅ Polars-first I/O pipeline
    ✅ Fully circular-safe (uses config_proxy, not config)
    ✅ Includes CLI self-test and runtime warning suppression
"""

from __future__ import annotations

import hashlib
import json
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List

import polars as pl

# ============================================================
# 🧭 Config + Logging Setup (circular-safe)
# ============================================================
from quant.utils.config_proxy import cfg_path
from quant.utils.logs import safe_log_init

# Suppress harmless double-import warnings for CLI self-run
warnings.filterwarnings("ignore", message=".*found in sys.modules.*")

logger = safe_log_init("IO")


# ============================================================
# 📂 Config-Aware Path Roots
# ============================================================
def _get_data_paths() -> tuple[Path, Path]:
    """Resolve static/runtime data dirs safely from config (via config_proxy)."""
    static = cfg_path("paths.data_static", "./data/static")
    runtime = cfg_path("paths.data_runtime", "./data/runtime")
    return static, runtime


def data_path(filename: str, *, static: bool = True) -> Path:
    """Resolve file inside /data/static or /data/runtime."""
    data_static, data_runtime = _get_data_paths()
    base = data_static if static else data_runtime
    path = (base / filename).expanduser().resolve()
    if not path.exists():
        logger.warning(f"[data_path] Missing file: {path}")
    return path


# ============================================================
# 📘 Loaders
# ============================================================
def load_json(filename: str, *, static: bool = True) -> dict[str, Any]:
    path = data_path(filename, static=static)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[LOAD_JSON_FAIL] {path.name}: {e.__class__.__name__} — {e}")
        return {}


def load_csv(filename: str, *, static: bool = True) -> pl.DataFrame:
    path = data_path(filename, static=static)
    try:
        return pl.read_csv(path)
    except Exception as e:
        logger.error(f"[LOAD_CSV_FAIL] {path.name}: {e}")
        return pl.DataFrame()


def load_parquet(filename: str, *, static: bool = True) -> pl.DataFrame:
    path = data_path(filename, static=static)
    try:
        return pl.read_parquet(path)
    except Exception as e:
        logger.error(f"[LOAD_PARQUET_FAIL] {path.name}: {e}")
        return pl.DataFrame()


# ============================================================
# 💾 Safe Write Context
# ============================================================
@contextmanager
def safe_open(path: Path, mode: str = "w") -> Generator[Any, None, None]:
    """Open file safely (ensuring parent dirs exist)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode, encoding="utf-8") as f:
        yield f


# ============================================================
# 🧩 Shared Symbol Load/Save
# ============================================================
def load_symbols_from_file(file_path: str | Path) -> List[str]:
    path = Path(file_path).expanduser().resolve()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("symbols", [])
        if isinstance(data, list):
            return data
        logger.warning(f"[LOAD_SYMBOLS] Unexpected structure: {path}")
        return []
    except FileNotFoundError:
        logger.warning(f"[LOAD_SYMBOLS] File not found: {path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"[LOAD_SYMBOLS] Invalid JSON {path}: {e}")
        return []
    except Exception as e:
        logger.error(f"[LOAD_SYMBOLS] Error: {e}")
        return []


# ============================================================
# 💾 Save Symbols (Atomic + Checksummed)
# ============================================================
def _compute_md5(obj: Any) -> str:
    try:
        payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.md5(payload).hexdigest()
    except Exception:
        return ""


def save_symbols_to_file(
    symbols: List[str] | Dict[str, Any], file_path: str | Path
) -> bool:
    path = Path(file_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"symbols": symbols} if isinstance(symbols, list) else symbols
    new_hash = _compute_md5(payload)
    old_hash = ""
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                old_hash = _compute_md5(json.load(f))
        except Exception:
            pass

    if new_hash and new_hash == old_hash:
        logger.debug(f"[UNCHANGED] {path.name} (MD5={new_hash[:8]})")
        return False

    tmp_path = path.with_suffix(".tmp")
    try:
        with safe_open(tmp_path, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        logger.info(
            f"[SAVED] {path.name} ({len(payload.get('symbols', []))} entries, MD5={new_hash[:8]})"
        )
        return True
    except Exception as e:
        logger.error(f"[SAVE_FAIL] {path}: {e}")
        return False


# ============================================================
# 🔍 File Change Tracker
# ============================================================
_FILE_TIMESTAMPS: dict[str, float] = {}


def has_file_changed(file_path: str | Path, checksum_check: bool = False) -> bool:
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        logger.warning(f"[FILE_CHECK] Missing: {path}")
        return False

    mtime = path.stat().st_mtime
    key = str(path)

    if key not in _FILE_TIMESTAMPS:
        _FILE_TIMESTAMPS[key] = mtime
        return True

    if mtime > _FILE_TIMESTAMPS[key]:
        _FILE_TIMESTAMPS[key] = mtime
        if checksum_check:
            try:
                with open(path, encoding="utf-8") as f:
                    md5 = _compute_md5(json.load(f))
                logger.info(f"[CHANGED] {path.name} (mtime+MD5={md5[:8]})")
            except Exception as e:
                logger.warning(f"[CHECKSUM_FAIL] {path.name}: {e}")
        else:
            logger.info(f"[CHANGED] {path.name} (mtime updated)")
        return True
    return False


# ============================================================
# 🧪 CLI Self-Test
# ============================================================
if __name__ == "__main__":
    print("🧩 Quant IO Self-Test (v2.5 Hybrid-Safe)")

    test_file = Path("./data/runtime/test_symbols.json")
    test_data = ["INFY", "RELIANCE", "TCS"]

    save_symbols_to_file(test_data, test_file)
    symbols = load_symbols_from_file(test_file)

    print(f"✅ Loaded {len(symbols)} symbols: {symbols}")
    print(f"📁 File path: {test_file.resolve()}")

    changed = has_file_changed(test_file)
    print(f"🔍 File change detected: {changed}")
