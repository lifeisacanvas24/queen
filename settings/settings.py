#!/usr/bin/env python3
# ============================================================
# queen/settings/settings.py — v9.3.0 (Unified Runtime + DRY Logging)
# Clean: no timeframe parsing here; use queen.settings.timeframes
# ============================================================
from __future__ import annotations

from pathlib import Path
from typing import Dict

from zoneinfo import ZoneInfo

from . import timeframes as TF

# ------------------------------------------------------------
# 🧩 Core Metadata
# ------------------------------------------------------------
APP = {
    "NAME": "Queen of Quant",
    "VERSION": "9.3.0",
    "BUILD": "2025.10.25",
    "AUTHOR": "OpenQuant Labs",
    "DESCRIPTION": "Unified Quant Engine — async, multi-threaded, and settings-first.",
}

# ------------------------------------------------------------
# 🌍 Environment Configuration
# ------------------------------------------------------------
ENV: str = "dev"  # default environment

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data"
STATIC = DATA / "static"

RUNTIME_PATHS: Dict[str, Dict[str, Path]] = {
    "dev": {
        "data_runtime": DATA / "runtime",
        "logs": DATA / "runtime" / "logs",
        "cache": DATA / "runtime" / "cache",
        "exports": DATA / "runtime" / "exports",
        "universe": DATA / "runtime" / "universe",
    },
    "prod": {
        "data_runtime": DATA / "runtime" / "prod",
        "logs": DATA / "runtime" / "prod" / "logs",
        "cache": DATA / "runtime" / "prod" / "cache",
        "exports": DATA / "runtime" / "prod" / "exports",
        "universe": DATA / "runtime" / "prod" / "universe",
    },
}


def set_env(mode: str) -> None:
    """Switch between dev/prod environments."""
    global ENV
    mode = mode.lower()
    if mode not in RUNTIME_PATHS:
        raise ValueError(f"Invalid env '{mode}'. Must be {list(RUNTIME_PATHS)}.")
    ENV = mode


def get_env() -> str:
    return ENV


def get_env_paths() -> Dict[str, Path]:
    return RUNTIME_PATHS[ENV]


# ------------------------------------------------------------
# 📁 Unified Path Map (logical locations)
# ------------------------------------------------------------
PATHS = {
    "ROOT": ROOT,
    "STATIC": STATIC,
    "CONFIGS": ROOT.parent / "configs",
    "RUNTIME": get_env_paths()["data_runtime"],
    "LOGS": get_env_paths()["logs"],
    "CACHE": get_env_paths()["cache"],
    "EXPORTS": get_env_paths()["exports"],
    "UNIVERSE": get_env_paths()["universe"],
    "SNAPSHOTS": get_env_paths()["cache"] / "snapshots",
    "INSTRUMENTS": STATIC / "instruments",
}

# ------------------------------------------------------------
# 🏦 Brokers (schema & rate limits)
# ------------------------------------------------------------
BROKERS = {
    "UPSTOX": {
        "API_SCHEMA": STATIC / "api_upstox.json",
        "RATE_LIMITS": {"PER_SECOND": 50, "PER_MINUTE": 500, "PER_30_MINUTE": 2000},
        "RETRY": {"MAX_RETRIES": 3, "TIMEOUT": 10, "BACKOFF_BASE": 2},
    },
    "ZERODHA": {
        "API_SCHEMA": STATIC / "api_zerodha.json",
        "RATE_LIMITS": {"PER_SECOND": 20, "PER_MINUTE": 200, "PER_30_MINUTE": 1000},
        "RETRY": {"MAX_RETRIES": 3, "TIMEOUT": 10, "BACKOFF_BASE": 2},
    },
}

# ------------------------------------------------------------
# 💹 Exchange & Market Hours
# ------------------------------------------------------------
EXCHANGE = {
    "ACTIVE": "NSE_BSE",
    "MARKET_TIMEZONE": "Asia/Kolkata",
    "EXCHANGES": {
        "NSE_BSE": {
            "NAME": "National Stock Exchange / Bombay Stock Exchange",
            "HOLIDAYS": STATIC / "nse_holidays.json",
            "ALL_NSE_SYMBOLS": STATIC / "all_nse_equity_list.csv",
            "ALL_BSE_SYMBOLS": STATIC / "all_bse_equity_list.csv",
            "INSTRUMENTS": {
                "INTRADAY": STATIC / "intraday_instruments.json",
                "WEEKLY": STATIC / "weekly_instruments.json",
                "MONTHLY": STATIC / "monthly_instruments.json",
                "PORTFOLIO": STATIC / "portfolio_instruments.json",
                "APPROVED_SYMBOLS": STATIC / "all_symbols.json",
            },
            "MARKET_HOURS": {
                "PRE_MARKET": "09:00",
                "OPEN": "09:15",
                "CLOSE": "15:30",
                "POST_MARKET": "23:59",
            },
            "TRADING_DAYS": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "EXPIRY_DAY": "Thursday",
        }
    },
}

MARKET_TZ = ZoneInfo(EXCHANGE["MARKET_TIMEZONE"])

# ------------------------------------------------------------
# ⚙️ Fetch / Scheduler knobs
# ------------------------------------------------------------
FETCH = {
    "ASYNC_MODE": True,
    "MAX_WORKERS": 8,
    "MAX_REQ_PER_SEC": 40,
    "MAX_REQ_PER_MIN": 400,
    "MAX_RETRIES": 3,
    "MAX_EMPTY_STREAK": 5,
    "BATCH_SIZE": 50,
}
SCHEDULER = {
    "DEFAULT_INTERVAL": "5m",
    "ALIGN_TO_CANDLE": True,
    "DEFAULT_BUFFER": 3,
    "REFRESH_MAP": {"1m": 15, "3m": 30, "5m": 30, "10m": 60, "15m": 60, "30m": 60},
}
SCHEDULER.update(
    {
        "ENABLE_UNIVERSE_REFRESH": False,
        "ENABLE_GRACEFUL_SHUTDOWN": False,
        "ENABLE_ERROR_BACKOFF": False,
    }
)

# ------------------------------------------------------------
# 🧠 Logging + Diagnostics
# ------------------------------------------------------------
LOGGING = {
    "LEVEL": "INFO",
    "ROTATE": True,
    "MAX_SIZE_MB": 25,
    "BACKUP_COUNT": 5,
    "FILES": {
        "CORE": "core_activity.log",
        "IO": "io_activity.log",
        "FETCH_ROUTER": "fetch_router.log",
        "FETCHER": "fetcher.log",
        "SCHEDULER": "scheduler.log",
        "UPSTOX_FETCHER": "upstox_fetcher.log",
        "MARKET": "market_activity.log",
        "INSTRUMENTS": "instruments_activity.log",
        "PATH_MANAGER": "path_manager.log",
        "SCHEMA_DRIFT_LOG": "schema_drift.json",
    },
}
DIAGNOSTICS = {
    "ENABLED": True,
    "FETCHER": {"URL_DEBUG": True, "TRACE_MARKET_STATE": True},
}

# ------------------------------------------------------------
# 🔩 Defaults (broker, exchange, mode defaults)
# ------------------------------------------------------------
DEFAULTS = {
    "BROKER": "UPSTOX",
    "EXCHANGE": "NSE_BSE",
    "SYMBOLS_LIMIT": 10,
    "AUTO_RESTART_DAEMON": True,
    "EXPORT_FORMAT": "parquet",
    # Intraday & Daily tokens are validated by timeframes.validate_tokens()
    "DEFAULT_INTERVALS": {"intraday": "5m", "daily": "1d"},
}

# ------------------------------------------------------------
# 🔔 Alert/Console defaults (heuristics + colors)
# ------------------------------------------------------------
DEFAULTS.update(
    {
        "ALERTS": {
            "COOLDOWN_SECONDS": 60,
            "DAILY_FALLBACK_BARS": 150,
            "INDICATOR_MIN_MULT": 3,
            "INDICATOR_MIN_FLOOR": 30,
            "PATTERN_CUSHION": 5,
            "PRICE_MIN_BARS": 5,
            # Optional explicit overrides per indicator:
            # "INDICATOR_MIN_BARS": {"rsi": 50, "macd": 90}
        },
        "CONSOLE_COLORS": {
            "green": "\x1b[32m",
            "red": "\x1b[31m",
            "yellow": "\x1b[33m",
            "cyan": "\x1b[36m",
            "reset": "\x1b[0m",
        },
    }
)

# ------------------------------------------------------------
# 🗂️ Ensure runtime folders exist
# ------------------------------------------------------------
for key, p in PATHS.items():
    try:
        Path(p).expanduser().resolve().mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# Optional instrument fallbacks to MONTHLY
try:
    _ex = EXCHANGE["EXCHANGES"][DEFAULTS.get("EXCHANGE", EXCHANGE["ACTIVE"])]
    ins = _ex.get("INSTRUMENTS", {})
    monthly = ins.get("MONTHLY")
    for _k in ("WEEKLY", "PORTFOLIO", "APPROVED_SYMBOLS"):
        _p = ins.get(_k)
        if _p and not Path(_p).exists() and monthly:
            ins[_k] = monthly
except Exception:
    pass


# ------------------------------------------------------------
# ✅ Settings self-check (call into timeframes)
# ------------------------------------------------------------
def _validate_defaults():
    # Broker & exchange must exist
    broker = DEFAULTS.get("BROKER")
    assert broker and broker.upper() in BROKERS, f"Unknown DEFAULTS.BROKER: {broker}"

    ex_key = DEFAULTS.get("EXCHANGE", EXCHANGE.get("ACTIVE"))
    assert ex_key in EXCHANGE["EXCHANGES"], f"Unknown DEFAULTS.EXCHANGE: {ex_key}"

    # Validate DEFAULT_INTERVALS using timeframes.py as the single owner
    di = DEFAULTS.setdefault("DEFAULT_INTERVALS", {"intraday": "5m", "daily": "1d"})
    try:
        TF.validate_token(di.get("intraday", "5m"))
        TF.validate_token(di.get("daily", "1d"))
    except Exception as e:
        raise AssertionError(f"Invalid DEFAULT_INTERVALS: {e}") from e


_validate_defaults()

# ------------------------------------------------------------
# 🔔 Alert sinks (single source of truth)
# ------------------------------------------------------------
ALERT_SINKS = {
    "JSONL": PATHS["EXPORTS"] / "alerts" / "alerts.jsonl",
    "YAML_RULES": PATHS["CONFIGS"] / "alert_rules.yaml",
    "SQLITE": PATHS["EXPORTS"] / "alerts" / "alerts.db",
    "SSE": "http://localhost:8000/alerts/stream",
    "STATE": PATHS["EXPORTS"] / "alerts" / "alerts_state.jsonl",
}


def alert_path_jsonl() -> Path:
    p = ALERT_SINKS["JSONL"]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def alert_path_sqlite() -> Path:
    p = ALERT_SINKS["SQLITE"]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def alert_path_rules() -> Path:
    p = ALERT_SINKS["YAML_RULES"]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def alert_path_state() -> Path:
    p = ALERT_SINKS["STATE"]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------
# 🧰 Small startup helper for daemons (optional)
# ------------------------------------------------------------
def print_effective_alert_knobs(print_fn=print) -> None:
    a = DEFAULTS.get("ALERTS", {})
    c = DEFAULTS.get("CONSOLE_COLORS", {})
    print_fn(
        f"[Settings] Alerts: cooldown={a.get('COOLDOWN_SECONDS')}s "
        f"| daily_fallback_bars={a.get('DAILY_FALLBACK_BARS')} "
        f"| indicator_min=(mult={a.get('INDICATOR_MIN_MULT')}, floor={a.get('INDICATOR_MIN_FLOOR')}) "
        f"| pattern_cushion={a.get('PATTERN_CUSHION')} | price_min_bars={a.get('PRICE_MIN_BARS')}"
    )
    # color keys listed just for visibility
    print_fn(f"[Settings] Console colors: {', '.join(sorted(c.keys()))}")


# ------------------------------------------------------------
# 🧩 Helper Functions (still valid in forward-only setup)
# ------------------------------------------------------------
def broker_config(name: str | None = None) -> Dict[str, Any]:
    """Return broker configuration by name (default from DEFAULTS)."""
    bname = (name or DEFAULTS.get("BROKER", "UPSTOX")).upper()
    return BROKERS.get(bname, {})


def market_hours(exchange: str | None = None) -> Dict[str, Any]:
    """Return MARKET_HOURS block for the active exchange."""
    ex = exchange or DEFAULTS.get("EXCHANGE", EXCHANGE["ACTIVE"])
    return EXCHANGE["EXCHANGES"].get(ex, {}).get("MARKET_HOURS", {})


def log_file(name: str) -> Path:
    """Resolve the log file path for a given logical name (case-insensitive)."""
    log_dir = PATHS["LOGS"]
    fname = LOGGING["FILES"].get(name.upper(), f"{name}.log")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / fname


def resolve_log_path(log_key: str) -> Path:
    """Alias wrapper for legacy usage (single-source)."""
    return log_file(log_key)


# ------------------------------------------------------------
# 🧪 Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"Environment: {get_env()}")
    print(f"Logs Directory: {PATHS['LOGS']}")
    print(f"Broker: {DEFAULTS['BROKER']}")
    print_effective_alert_knobs()
