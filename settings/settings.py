#!/usr/bin/env python3
# ============================================================
# queen/settings/settings.py — v9.1 (Restored + DRY, Python-only)
# ============================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

# ------------------------------------------------------------
# 🧭 Environment
#   QUANT_ENV controls dev/prod path roots (default: dev)
#   Values: "dev", "prod"
# ------------------------------------------------------------
_ENV = os.getenv("QUANT_ENV", "dev").strip().lower()
if _ENV not in {"dev", "prod"}:
    _ENV = "dev"


def get_env() -> str:
    return _ENV


def set_env(value: str) -> None:
    global _ENV
    _ENV = (value or "dev").strip().lower()
    if _ENV not in {"dev", "prod"}:
        _ENV = "dev"


# ------------------------------------------------------------
# 📁 Paths (project-relative; no imports from helpers)
#   Matches your desired layout under queen/data/...
# ------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]

_ENV_BASE = {
    "dev": _REPO_ROOT / "queen" / "data" / "runtime",
    "prod": _REPO_ROOT / "queen" / "data" / "runtime" / "prod",
}
BASE_RUNTIME = _ENV_BASE[get_env()]


def _mk(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


PATHS: Dict[str, Path] = {
    "ROOT": _REPO_ROOT,
    "RUNTIME": _mk(BASE_RUNTIME),
    "LOGS": _mk(BASE_RUNTIME / "logs"),
    "SNAPSHOTS": _mk(BASE_RUNTIME / "snapshots"),
    "EXPORTS": _mk(BASE_RUNTIME / "exports"),
    "ALERTS": _mk(BASE_RUNTIME / "exports" / "alerts"),
    "FETCH_OUTPUTS": _mk(BASE_RUNTIME / "exports" / "fetch_outputs"),
    "CACHE": _mk(BASE_RUNTIME / "cache"),
    "MODELS": _mk(BASE_RUNTIME / "cache" / "models"),
    "MODEL_SNAPSHOTS": _mk(BASE_RUNTIME / "cache" / "models" / "snapshots"),
    "TEST_HELPERS": _mk(BASE_RUNTIME / "test_helpers"),
    # static + project resources
    "STATIC": _REPO_ROOT / "queen" / "data" / "static",
    "PROFILES": _REPO_ROOT / "queen" / "data" / "static" / "profiles",
    "CONFIGS": _REPO_ROOT / "configs",
    # 🔑 NEW (needed by instruments/universe helpers)
    "UNIVERSE": _mk(BASE_RUNTIME / "universe"),
}

# ------------------------------------------------------------
# 🧩 App / Defaults / Brokers / Fetch / Scheduler / Logging
# ------------------------------------------------------------
APP = {"name": "Queen of Quant", "version": "v9.1", "env": get_env()}

DEFAULTS: Dict[str, Any] = {
    "BROKER": "upstox",
    "SYMBOLS_LIMIT": 10,
    "AUTO_RESTART_DAEMON": True,
    # EXCHANGE is set after EXCHANGE block (see below)
}

BROKERS = {
    "upstox": {
        "retry": {"max_retries": 3, "timeout": 10, "backoff_base": 2},
        "rate_limits": {
            "max_per_second": 50,
            "max_per_minute": 500,
            "max_per_30_minute": 2000,
        },
        # Keep snake_case here, but downstream code should accept both api_schema/API_SCHEMA
        "api_schema": str(PATHS["STATIC"] / "api_upstox.json"),
    },
    "zerodha": {
        "retry": {"max_retries": 3, "timeout": 10, "backoff_base": 2},
        "rate_limits": {
            "max_per_second": 20,
            "max_per_minute": 200,
            "max_per_30_minute": 1000,
        },
        "api_schema": str(PATHS["STATIC"] / "api_zerodha.json"),
    },
}

FETCH = {
    "max_workers": 8,
    "max_req_per_sec": 40,
    "max_req_per_min": 400,
    "max_retries": 3,
    "max_empty_streak": 5,
}

SCHEDULER = {
    "default_interval": "5m",
    "default_buffer": 3,
    "align_to_candle": True,
    "refresh_map": {"1m": 15, "3m": 30, "5m": 30, "10m": 60, "15m": 60, "30m": 60},
}

LOGGING = {
    "LEVEL": "INFO",
    "ROTATE_ENABLED": True,
    "MAX_SIZE_MB": 25,
    "BACKUP_COUNT": 5,
    "FILES": {
        "CORE": "core_activity.log",
        "IO": "io_activity.log",
        "FETCH_ROUTER": "fetch_router_activity.log",
        "FETCHER": "fetch_activity.log",
        "CANDLE_ADAPTER": "candle_adapter_activity.log",
        "UPSTOX_FETCHER": "upstox_fetcher_activity.log",
        "SCHEDULER": "scheduler_activity.log",
        "COCKPIT": "cockpit_snapshot.log",
        "METRICS": "metrics_engine.log",
        "CONFIG_WATCHER": "config_watcher.log",
        "DATAFRAME": "dataframe_activity.log",
        "MARKET": "market_activity.log",
        "INSTRUMENTS": "instruments_activity.log",
        "HOLIDAYS": "holidays_activity.log",
        "VERIFY": "verify_activity.log",
        "PATHMANAGER": "path_manager.log",
        "SCHEMA": "schema_drift.log",
        "RATELIMITER": "rate_limiter.log",
    },
}

DIAGNOSTICS = {
    "ENABLED": True,
    "FETCHER": {
        "url_debug": True,
        "payload_preview": False,
        "max_preview_bytes": 512,
        "trace_market_state": True,
    },
    "CACHE": {"auto_rotate": True, "max_snapshots": 3},
}

# ------------------------------------------------------------
# 🏛️ Exchange (calendar + instruments)
# ------------------------------------------------------------
EXCHANGE = {
    "MARKET_TIMEZONE": "Asia/Kolkata",
    "EXCHANGES": {
        "NSE_BSE": {
            "MARKET_HOURS": {
                "PRE_MARKET": "09:00",
                "OPEN": "09:15",
                "CLOSE": "15:30",
                "POST_MARKET": "23:59",
            },
            "TRADING_DAYS": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "EXPIRY_DAY": "Thursday",
            # 🌅 Calendar file
            "HOLIDAYS": str(PATHS["STATIC"] / "nse_holidays.json"),
            # 📘 Instruments & Universe
            "INSTRUMENTS": {
                # JSON-based primary sources
                "MONTHLY": str(PATHS["STATIC"] / "monthly_instruments.json"),
                "WEEKLY": str(PATHS["STATIC"] / "monthly_instruments.json"),
                "INTRADAY": str(PATHS["STATIC"] / "intraday_instruments.json"),
                # CSV-based Universe & portfolio lists
                "PORTFOLIO": str(PATHS["UNIVERSE"] / "portfolio.csv"),
                # Combined approved list — only unique symbols merged from NSE & BSE universes
                "APPROVED_SYMBOLS": str(PATHS["UNIVERSE"] / "approved_symbols.csv"),
                # Source universes — raw lists from each exchange
                "NSE_UNIVERSE": str(PATHS["UNIVERSE"] / "nse_universe.csv"),
                "BSE_UNIVERSE": str(PATHS["UNIVERSE"] / "bse_universe.csv"),
            },
        },
    },
    "ACTIVE": "NSE_BSE",
}

# Ensure DEFAULTS carries the active exchange key used by helpers
DEFAULTS["EXCHANGE"] = EXCHANGE.get("ACTIVE", "NSE_BSE")


# ------------------------------------------------------------
# 🔎 Access helpers (no heavy imports to avoid circulars)
# ------------------------------------------------------------
def log_file(name: str) -> Path:
    """Return resolved path for a named log stream (e.g., 'CORE')."""
    fname = LOGGING.get("FILES", {}).get(name.upper(), f"{name.lower()}.log")
    PATHS["LOGS"].mkdir(parents=True, exist_ok=True)
    return PATHS["LOGS"] / fname


def resolve_log_path(name: str) -> Path:
    """Alias of log_file(name), kept for back-compat calls in code."""
    return log_file(name)


def broker_config(name: str | None = None) -> Dict[str, Any]:
    """Return broker mapping for the active/default broker."""
    key = (name or DEFAULTS.get("BROKER", "upstox")).lower()
    return BROKERS.get(key, {})


def market_timezone() -> str:
    return EXCHANGE.get("MARKET_TIMEZONE", "Asia/Kolkata")


def active_exchange() -> str:
    return EXCHANGE.get("ACTIVE", "NSE_BSE")


def exchange_info(name: str | None = None) -> dict:
    name = name or active_exchange()
    return (EXCHANGE.get("EXCHANGES") or {}).get(name, {})


def market_hours() -> Dict[str, str]:
    """Return hours for the active exchange (PRE_MARKET/OPEN/CLOSE/POST_MARKET)."""
    info = exchange_info()
    return info.get("MARKET_HOURS", {})


# Alert sink paths (several modules referenced these names earlier)
def alert_path_jsonl() -> Path:
    return PATHS["ALERTS"] / "alerts.jsonl"


def alert_path_sqlite() -> Path:
    return PATHS["ALERTS"] / "alerts.sqlite"


def alert_path_rules() -> Path:
    return PATHS["ALERTS"] / "rules.yml"


def alert_path_state() -> Path:
    return PATHS["ALERTS"] / "state.json"


# Convenience: return useful paths for meta/strategy snapshots
def get_env_paths() -> Dict[str, Path]:
    return {
        "runtime": PATHS["RUNTIME"],
        "logs": PATHS["LOGS"],
        "exports": PATHS["EXPORTS"],
        "alerts": PATHS["ALERTS"],
        "fetch_outputs": PATHS["FETCH_OUTPUTS"],
        "cache": PATHS["CACHE"],
        "models": PATHS["MODELS"],
        "model_snapshots": PATHS["MODEL_SNAPSHOTS"],
        "snapshots": PATHS["SNAPSHOTS"],
        "universe": PATHS["UNIVERSE"],
        "static": PATHS["STATIC"],
    }


# Optional registries (safe empty defaults)
METRICS: Dict[str, Any] = {}
TACTICAL: Dict[str, Any] = {}
PROFILES: Dict[str, Any] = {}
TIMEFRAMES: Dict[str, Any] = {}
REGIMES: Dict[str, Any] = {}
