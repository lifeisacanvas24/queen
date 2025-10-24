#!/usr/bin/env python3
# ============================================================
# quant/utils/common.py — Quant-Core Universal Helpers (v5.0 — Hybrid-Safe)
# ============================================================
"""Purpose:
    Core low-level utilities shared across Quant-Core v8+ subsystems.

Features:
    ✅ Safe Polars/NumPy/JSON conversions
    ✅ Async-safe retry + delay primitives
    ✅ Config-proxy based (no circular config imports)
    ✅ Diagnostics-aware structured logging
    ✅ System health + batching utilities
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Iterable, List, Optional

import numpy as np
import polars as pl

# 🔄 New hybrid-safe config + logging
from quant.utils.config_proxy import cfg_bool, cfg_get, cfg_path
from quant.utils.logs import safe_log_init

# ============================================================
# 🧭 Logging & Diagnostics
# ============================================================
logger = safe_log_init("CommonUtils")

DIAG_ENABLED = cfg_bool("diagnostics.enabled", True)
TRACE_IO = cfg_bool("diagnostics.common.trace_io", False)

# Pre-resolve default log path
try:
    LOG_DIR = cfg_path("paths.logs", "./data/runtime/logs")
    LOG_FILE = cfg_get("logging.files.common", "common_activity.log")
    _LOG_FILE = LOG_DIR / LOG_FILE
except Exception:
    _LOG_FILE = Path("./data/runtime/logs/common_activity.log").resolve()


# ============================================================
# 🧩 DataFrame Utilities
# ============================================================
def is_empty(df: Optional[pl.DataFrame]) -> bool:
    """Return True if DataFrame is None or has zero rows."""
    empty = df is None or getattr(df, "height", 0) == 0
    if empty and DIAG_ENABLED:
        logger.debug("DataFrame is empty or None.")
    return empty


def preview_rows(df: Optional[pl.DataFrame], n: int = 3) -> str:
    """Return short printable preview for logging."""
    if is_empty(df):
        return "(empty)"
    try:
        txt = df.head(n).to_string()
        if DIAG_ENABLED:
            logger.debug(f"Preview first {n} rows:\n{txt}")
        return txt
    except Exception as e:
        logger.warning(f"[preview_rows] Failed: {e}")
        return f"(preview error: {e})"


# ============================================================
# 🔢 Scalar & JSON-Safe Conversions
# ============================================================
def as_scalar(val: Any) -> Any:
    """Convert NumPy/Polars scalar into native Python scalar."""
    if hasattr(val, "item"):
        try:
            return val.item()
        except Exception:
            return val
    return val


def to_py(val: Any) -> Any:
    """Recursively ensure any structure is JSON-serializable."""
    try:
        if isinstance(val, pl.Series):
            vals = val.to_list()
            return to_py(vals[0]) if len(vals) == 1 else [to_py(v) for v in vals]
        if isinstance(val, np.generic):
            return val.item()
        if hasattr(val, "item") and not isinstance(val, (list, tuple, dict, pl.Series)):
            return val.item()
        if isinstance(val, (list, tuple)):
            return [to_py(v) for v in val]
        if isinstance(val, dict):
            return {k: to_py(v) for k, v in val.items()}
        return val
    except Exception as e:
        logger.error(f"[to_py] Failed for {val!r}: {e}")
        return str(val)


# ============================================================
# 📁 File & Path Utilities
# ============================================================
def ensure_dir(path: str | Path) -> Path:
    """Ensure directory exists and return resolved Path."""
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_from_config(key: str) -> Path:
    """Resolve a path via config_proxy and ensure its parent exists."""
    path = cfg_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Safely load JSON with diagnostics."""
    p = Path(path)
    if not p.exists():
        if DIAG_ENABLED:
            logger.debug(f"[safe_json_load] File not found: {p}")
        return default
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
            if TRACE_IO:
                logger.info(f"[IO] Loaded JSON: {p.name} ({len(str(data))} bytes)")
            return data
    except Exception as e:
        logger.warning(f"[safe_json_load] Failed for {p}: {e}")
        return default


def safe_json_save(path: str | Path, data: Any, indent: int = 2) -> bool:
    """Safely write JSON atomically."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        tmp.replace(p)
        if TRACE_IO:
            logger.info(f"[IO] Saved JSON: {p.name} ({len(str(data))} bytes)")
        return True
    except Exception as e:
        logger.error(f"[safe_json_save] Failed for {path}: {e}")
        return False


# ============================================================
# 🧠 Async Helpers
# ============================================================
async def async_safe_sleep(sec: float, jitter: float = 0.05) -> None:
    """Async sleep with jitter for rate control."""
    await asyncio.sleep(sec + random.uniform(0, jitter))


async def retry_async(fn, retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry async function with exponential backoff."""
    for i in range(1, retries + 1):
        try:
            return await fn()
        except Exception as e:
            if i == retries:
                logger.error(f"[retry_async] Final failure: {e}")
                raise
            wait = delay * (backoff ** (i - 1))
            logger.warning(
                f"[retry_async] Attempt {i} failed: {e}, retrying in {wait:.2f}s"
            )
            await async_safe_sleep(wait)


# ============================================================
# 🧮 Collection Utilities
# ============================================================
def chunk_list(seq: Iterable[Any], size: int) -> List[list[Any]]:
    """Split iterable into chunks of given size."""
    seq = list(seq)
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def flatten(nested: Iterable[Iterable[Any]]) -> list[Any]:
    """Flatten list of lists safely."""
    return [x for sub in nested for x in sub]


# ============================================================
# 🖥️ System Health Utilities
# ============================================================
def get_system_uptime() -> dict[str, str | float]:
    """Return system uptime and memory/load stats (psutil optional)."""
    uptime_sec = 0.0
    load_avg = (0.0, 0.0, 0.0)
    mem_used_gb = mem_total_gb = 0.0

    try:
        import psutil

        uptime_sec = float(time.time() - psutil.boot_time())
        mem = psutil.virtual_memory()
        mem_used_gb = round(mem.used / (1024**3), 2)
        mem_total_gb = round(mem.total / (1024**3), 2)

        if hasattr(os, "getloadavg"):
            load_avg = tuple(round(x, 2) for x in os.getloadavg())
    except Exception:
        pass

    return {
        "seconds": uptime_sec,
        "formatted": str(dt.timedelta(seconds=int(uptime_sec))),
        "load_avg": load_avg,
        "mem_used_gb": mem_used_gb,
        "mem_total_gb": mem_total_gb,
    }


def get_system_snapshot() -> dict[str, Any]:
    """Return a structured snapshot for diagnostics telemetry."""
    snap = get_system_uptime()
    snap["timestamp"] = dt.datetime.now().isoformat()
    snap["cwd"] = str(Path.cwd())
    snap["pid"] = os.getpid()
    return snap


# ============================================================
# 🧪 Self-Test
# ============================================================
if __name__ == "__main__":
    print("🧩 Quant-Core Common v5.0 Self-Test")
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    print("is_empty(df):", is_empty(df))
    print("Preview:", preview_rows(df))
    print("Scalar:", as_scalar(np.int64(42)))
    data = {"x": 1, "y": [1, 2, 3]}
    tmp = Path("./data/runtime/test_common.json")
    safe_json_save(tmp, data)
    print("Reloaded:", safe_json_load(tmp))
    print("Chunk:", chunk_list(range(7), 3))
    print("Snapshot:", get_system_snapshot())
