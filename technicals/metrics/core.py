# ============================================================
# queen/technicals/metrics/core.py — Auto-Discovery Metrics Engine (v2.1)
# ============================================================
"""Quant-Core Metrics Engine — Config-Driven + Auto-Discovery

Discovers and executes all compute_*() metric functions inside
quant/metrics/*.py, as defined in configs/metrics.json.

Features:
    ✅ Config-driven enable/disable toggles
    ✅ Auto-discovery of compute_*() modules
    ✅ Graceful error handling and logging
    ✅ Auto-rounding and timestamping
"""

from __future__ import annotations

import datetime as dt
import importlib
import inspect
import pkgutil
from pathlib import Path

import polars as pl
import pytz
from quant import config
from quant.utils.logs import get_logger

logger = get_logger("MetricsCore")

# ============================================================
# 🧩 Dynamic Metric Function Discovery
# ============================================================


def _discover_metric_functions() -> dict[str, callable]:
    """Scan quant.metrics.* for compute_*() functions."""
    import quant.metrics as metrics_pkg

    discovered = {}
    base_path = Path(metrics_pkg.__file__).parent

    for _, module_name, is_pkg in pkgutil.iter_modules([str(base_path)]):
        if is_pkg or module_name == "core":
            continue
        try:
            module = importlib.import_module(f"quant.metrics.{module_name}")
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("compute_"):
                    discovered[name] = func
        except Exception as e:
            logger.warning(f"⚠️ Failed to import metric module '{module_name}': {e}")
    return discovered


_DISCOVERED_FUNCS = None


def get_metric_functions(force_refresh: bool = False) -> dict[str, callable]:
    """Cached discovery of all compute_*() metric functions."""
    global _DISCOVERED_FUNCS
    if _DISCOVERED_FUNCS is None or force_refresh:
        _DISCOVERED_FUNCS = _discover_metric_functions()
    return _DISCOVERED_FUNCS


# ============================================================
# 🧮 Main Entry Point — Compute All Metrics
# ============================================================


def compute_all_metrics(df: pl.DataFrame, interval: str = "5m") -> dict:
    if df.is_empty():
        logger.warning("⚠️ Empty DataFrame passed to Metrics Engine.")
        return {}

    metrics = {
        "timestamp": dt.datetime.now(pytz.timezone("Asia/Kolkata")).isoformat(
            timespec="seconds"
        ),
        "interval": interval,
        "symbol_count": len(df),
    }

    try:
        metrics_cfg_path = config.get_path(
            "paths.metrics_config", fallback="./configs/metrics.json"
        )
        metrics_cfg = config.load_json(metrics_cfg_path)  # <— ✅ FIX
        enabled = set(metrics_cfg.get("enabled", []))
    except Exception as e:
        logger.error(f"[Metrics] Failed to load metrics config: {e}")
        enabled = set()


# ============================================================
# 🧠 Example Metric Function (for developers)
# ============================================================
# def compute_avg_close(df: pl.DataFrame) -> dict:
#     if "close" not in df.columns:
#         return {}
#     return {"avg_close": float(df["close"].mean())}
