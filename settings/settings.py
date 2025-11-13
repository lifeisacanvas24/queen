#!/usr/bin/env python3
# ============================================================
# queen/settings/settings.py — v9.3 (DRY, env-aware, forward-only)
# ============================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

# ------------------------------------------------------------
# 🧭 Environment
#   QUEEN_ENV controls dev/prod path roots (default: dev)
#   Values: "dev", "prod"
# ------------------------------------------------------------
_ENV = os.getenv("QUEEN_ENV", "dev").strip().lower()
if _ENV not in {"dev", "prod"}:
    _ENV = "dev"

def get_env() -> str:
    return _ENV

# ------------------------------------------------------------
# 📁 Paths (project-relative; no imports from helpers)
# ------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]

def _env_base(env: str) -> Path:
    env = (env or "dev").strip().lower()
    if env not in {"dev", "prod"}:
        env = "dev"
    return (_REPO_ROOT / "queen" / "data" / "runtime") if env == "dev" \
        else (_REPO_ROOT / "queen" / "data" / "runtime" / "prod")

def _mk(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def _build_paths(env: str) -> Dict[str, Path]:
    base_runtime = _env_base(env)
    return {
        "ROOT": _REPO_ROOT,
        "RUNTIME": _mk(base_runtime),
        "LOGS": _mk(base_runtime / "logs"),
        "SNAPSHOTS": _mk(base_runtime / "snapshots"),
        "EXPORTS": _mk(base_runtime / "exports"),
        "ALERTS": _mk(base_runtime / "exports" / "alerts"),
        "FETCH_OUTPUTS": _mk(base_runtime / "exports" / "fetch_outputs"),
        "CACHE": _mk(base_runtime / "cache"),
        "MODELS": _mk(base_runtime / "cache" / "models"),
        "MODEL_SNAPSHOTS": _mk(base_runtime / "cache" / "models" / "snapshots"),
        "TEST_HELPERS": _mk(base_runtime / "test_helpers"),
        # static + project resources
        "STATIC": _REPO_ROOT / "queen" / "data" / "static",
        "INSTRUMENTS": _REPO_ROOT / "queen" / "data" / "static",
        "UNIVERSE": _REPO_ROOT / "queen" / "data" / "static",
        "PROFILES": _REPO_ROOT / "queen" / "data" / "static" / "profiles",
        "CONFIGS": _REPO_ROOT / "configs",
        "TEMPLATES": _mk(_REPO_ROOT / "queen" / "server" / "templates"),
    }

PATHS: Dict[str, Path] = _build_paths(get_env())

def set_env(value: str) -> None:
    """Switch environment AND rebuild PATHS (forward-only)."""
    global _ENV, PATHS
    new_env = (value or "dev").strip().lower()
    if new_env not in {"dev", "prod"}:
        new_env = "dev"
    if new_env == _ENV:
        return
    _ENV = new_env
    PATHS = _build_paths(_ENV)

# ------------------------------------------------------------
# 🧩 App / Defaults / Brokers / Fetch / Scheduler / Logging
# ------------------------------------------------------------
APP = {"name": "Queen of Quant", "version": "v9.3", "env": get_env()}

# ------------------------------------------------------------
# 🌐 External APIs (HTTP endpoints)
# ------------------------------------------------------------
EXTERNAL_APIS = {
    "NSE": {
        "BASE_URL": "https://www.nseindia.com",
        "QUOTE_EQUITY": "/api/quote-equity?symbol={symbol}",
        "QUOTE_REFERER": "/get-quotes/equity?symbol={symbol}",
    },
}

DEFAULTS: Dict[str, Any] = {
    "BROKER": "upstox",
    "SYMBOLS_LIMIT": 10,
    "AUTO_RESTART_DAEMON": True,
    "ALERTS": {
        "INDICATOR_MIN_MULT": 3,    # multiply 'length' by this
        "INDICATOR_MIN_FLOOR": 30,  # lower bound on bars, regardless of length
    },
    # EXCHANGE is set after EXCHANGE block (see below)
}

# -- Used by helpers.broker_config(); schema paths resolved via PATHS
BROKERS = {
    "upstox": {
        "retry": {"max_retries": 3, "timeout": 10, "backoff_base": 2},
        "rate_limits": {"max_per_second": 50, "max_per_minute": 500, "max_per_30_minute": 2000},
        "api_schema": str(PATHS["STATIC"] / "api_upstox.json"),
    },
    "zerodha": {
        "retry": {"max_retries": 3, "timeout": 10, "backoff_base": 2},
        "rate_limits": {"max_per_second": 20, "max_per_minute": 200, "max_per_30_minute": 1000},
        "api_schema": str(PATHS["STATIC"] / "api_zerodha.json"),
    },
}

# -------------------- FETCH knobs (discoverability) --------------------
# Read by:
#   • fetchers/upstox_fetcher.py → _min_rows_from_settings() for intraday thinness thresholds
#   • fetch_router.py → MAX_WORKERS for concurrency limits
# Notes:
#   - Per-timeframe keys use upper-cased tokens (e.g., MIN_ROWS_AUTO_BACKFILL_5M, _1H)
#   - "MIN_ROWS_AUTO_BACKFILL" is a global fallback if specific keys are absent
FETCH = {
    "max_workers": 8,
    "max_req_per_sec": 40,
    "max_req_per_min": 400,
    "max_retries": 3,
    "max_empty_streak": 5,

    # Optional min-row thresholds (commented examples):
    # "MIN_ROWS_AUTO_BACKFILL": 80,
    # "MIN_ROWS_AUTO_BACKFILL_1M": 180,
    # "MIN_ROWS_AUTO_BACKFILL_3M": 140,
    # "MIN_ROWS_AUTO_BACKFILL_5M": 120,
    # "MIN_ROWS_AUTO_BACKFILL_10M": 100,
    # "MIN_ROWS_AUTO_BACKFILL_15M": 80,
    # "MIN_ROWS_AUTO_BACKFILL_30M": 60,
    # "MIN_ROWS_AUTO_BACKFILL_1H": 40,
    # "MIN_ROWS_AUTO_BACKFILL_2H": 30,
    # "MIN_ROWS_AUTO_BACKFILL_4H": 20,
}

# ----------------- SCHEDULER knobs (discoverability) -------------------
# Read by:
#   • daemons/scheduler.py:
#         - INTERVAL_MINUTES          (loop cadence for intraday)
#         - DEFAULT_MODE              ("intraday" | "daily")
#         - MAX_SYMBOLS               (universe cap per cycle)
#         - UNIVERSE_REFRESH_MINUTES  (periodic reload of instruments, 0=off)
#         - LOG_UNIVERSE_STATS        (log universe counts + diffs on refresh)
#   • fetch_router.py:
#         - default_interval (token like '5m') via helpers.parse_minutes()
#         - refresh_map (optional: alignment cadence per token)
SCHEDULER = {
    "default_interval": "5m",
    "default_buffer": 3,
    "align_to_candle": True,
    "refresh_map": {"1m": 15, "3m": 30, "5m": 30, "10m": 60, "15m": 60, "30m": 60},

    "INTERVAL_MINUTES": 5,
    "DEFAULT_MODE": "intraday",
    "MAX_SYMBOLS": 250,
    "UNIVERSE_REFRESH_MINUTES": 60,
    "LOG_UNIVERSE_STATS": True,
}

LOGGING = {
    "LEVEL": "INFO",
    "ROTATE_ENABLED": True,
    "MAX_SIZE_MB": 25,
    "BACKUP_COUNT": 5,
    "CONSOLE_ENABLED": True,
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

            # 📘 Instruments — STATIC JSONs (source of truth)
            #   intraday_instruments.json
            #   monthly_instruments.json
            #   weekly_instruments.json (optional)
            "INSTRUMENTS": {
                          "MONTHLY":   str(PATHS["STATIC"] / "monthly_instruments.json"),
                          "WEEKLY":    str(PATHS["STATIC"] / "monthly_instruments.json"),
                          "INTRADAY":  str(PATHS["STATIC"] / "intraday_instruments.json"),
                          # optional universe/portfolio stuff:
                          "PORTFOLIO": str(PATHS["UNIVERSE"] / "portfolio.csv"),
                          "APPROVED_SYMBOLS": str(PATHS["UNIVERSE"] / "approved_symbols.csv"),
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

# Alert sink paths
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

# ------------------------------------------------------------
# Optional registries (safe empty defaults)
# (Keep data here minimal to avoid circular deps; real configs live in their modules)
# ------------------------------------------------------------
METRICS: Dict[str, Any] = {}
TACTICAL: Dict[str, Any] = {}
PROFILES: Dict[str, Any] = {}
TIMEFRAMES: Dict[str, Any] = {}
REGIMES: Dict[str, Any] = {}
INDICATORS: Dict[str, Any] = {}
META_LAYERS: Dict[str, Any] = {}
