#!/usr/bin/env python3
# ============================================================
# queen/settings/settings.py — v9.1 (Unified Runtime + DRY Logging)
# ============================================================
"""Queen of Quant — Unified Configuration System
------------------------------------------------
Design goals:
✅ Fully Pythonic (no external config) with comments & computed defaults
✅ Environment-aware (DEV / PROD) paths
✅ Single source of truth for brokers/exchange/paths
✅ Early validation for common footguns (timeframes, defaults, existence)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from zoneinfo import ZoneInfo

# ------------------------------------------------------------
# 🧩 Core Metadata
# ------------------------------------------------------------
APP = {
    "NAME": "Queen of Quant",
    "VERSION": "9.1.0",
    "BUILD": "2025.10.24",
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
    """Return current environment."""
    return ENV


def get_env_paths() -> Dict[str, Path]:
    """Return active environment paths."""
    return RUNTIME_PATHS[ENV]


# ------------------------------------------------------------
# 📁 Unified Path Map (logical locations)
# ------------------------------------------------------------
PATHS = {
    "ROOT": ROOT,
    "STATIC": STATIC,
    "CONFIGS": ROOT / "configs",
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
}
# Default mode intervals the FETCHER will apply when router passes interval=None
DEFAULTS.setdefault("DEFAULT_INTERVALS", {"intraday": "5m", "daily": "1d"})
_intr = DEFAULTS["DEFAULT_INTERVALS"].get("intraday", "5m")
_daily = DEFAULTS["DEFAULT_INTERVALS"].get("daily", "1d")
for tok in (_intr, _daily):
    assert isinstance(tok, str) and len(tok) >= 2, f"Bad interval token: {tok}"

# ------------------------------------------------------------
# 🗂️ Ensure runtime folders exist (once, on import)
# ------------------------------------------------------------
for key, p in PATHS.items():
    try:
        Path(p).expanduser().resolve().mkdir(parents=True, exist_ok=True)
    except Exception:
        # paths pointing to files will be created later by IO atomic writes
        pass

# Make optional instrument lists fall back to MONTHLY if missing
try:
    _ex = EXCHANGE["EXCHANGES"][DEFAULTS.get("EXCHANGE", EXCHANGE["ACTIVE"])]
    ins = _ex.get("INSTRUMENTS", {})
    monthly = ins.get("MONTHLY")
    for _k in ("WEEKLY", "PORTFOLIO", "APPROVED_SYMBOLS"):
        _p = ins.get(_k)
        if _p and not Path(_p).exists() and monthly:
            ins[_k] = monthly
except Exception:
    # purely defensive
    pass

# ------------------------------------------------------------
# 🕒 Timeframe map (friendly → canonical the fetcher understands)
# ------------------------------------------------------------
TIMEFRAME_MAP = {
    "1m": "minutes:1",
    "5m": "minutes:5",
    "15m": "minutes:15",
    "1h": "hours:1",
    "2h": "hours:2",
    "4h": "hours:4",
    "1d": "days:1",
    "1w": "weeks:1",
    "1mo": "months:1",
}
_allowed_units = {"minutes", "hours", "days", "weeks", "months"}
for k, v in TIMEFRAME_MAP.items():
    if ":" in v:
        u, n = v.split(":", 1)
        assert (
            u in _allowed_units and n.isdigit() and int(n) > 0
        ), f"Bad timeframe map: {k}->{v}"
    else:
        # tolerate suffix-style values if ever added later
        assert v.endswith(("m", "h", "d", "w", "o")), f"Bad timeframe map: {k}->{v}"


# ------------------------------------------------------------
# ✅ Settings self-check (early fail for misconfig)
# ------------------------------------------------------------
def _validate_defaults():
    # Broker & exchange must exist
    broker = DEFAULTS.get("BROKER")
    assert broker and broker.upper() in BROKERS, f"Unknown DEFAULTS.BROKER: {broker}"

    ex_key = DEFAULTS.get("EXCHANGE", EXCHANGE.get("ACTIVE"))
    assert ex_key in EXCHANGE["EXCHANGES"], f"Unknown DEFAULTS.EXCHANGE: {ex_key}"

    # DEFAULT_INTERVALS must be friendly tokens like 5m/1h/1d/1w/1mo
    di = DEFAULTS.setdefault("DEFAULT_INTERVALS", {"intraday": "5m", "daily": "1d"})

    def _ok(tok: str) -> bool:
        s = str(tok).lower()
        # accept 5m / 1h / 1d / 1w / 1mo
        if s.endswith("mo"):
            return s[:-2].isdigit() and int(s[:-2]) > 0
        return s.endswith(("m", "h", "d", "w")) and s[:-1].isdigit() and int(s[:-1]) > 0

    assert _ok(
        di.get("intraday", "5m")
    ), "DEFAULT_INTERVALS.intraday must be like '5m' or '1h'"
    assert _ok(
        di.get("daily", "1d")
    ), "DEFAULT_INTERVALS.daily must be like '1d'/'1w'/'1mo'"


_validate_defaults()


# ------------------------------------------------------------
# 🧩 Helper Functions
# ------------------------------------------------------------
def broker_config(name: str | None = None) -> Dict[str, Any]:
    return BROKERS.get((name or DEFAULTS["BROKER"]).upper(), {})


def market_hours(exchange: str | None = None) -> Dict[str, Any]:
    ex = exchange or DEFAULTS.get("EXCHANGE", EXCHANGE["ACTIVE"])
    return EXCHANGE["EXCHANGES"].get(ex, {}).get("MARKET_HOURS", {})


def log_file(name: str) -> Path:
    """Resolve log file path by name via settings."""
    log_dir = PATHS["LOGS"]
    file_name = LOGGING["FILES"].get(name.upper(), f"{name}.log")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / file_name


def resolve_log_path(log_key: str) -> Path:
    """Resolve any log or drift path safely."""
    return log_file(log_key)


# ------------------------------------------------------------
# 🧪 Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"Environment: {get_env()}")
    print(f"Logs Directory: {PATHS['LOGS']}")
    print(f"Broker: {DEFAULTS['BROKER']}")
    print(f"Schema Drift Log: {resolve_log_path('SCHEMA_DRIFT_LOG')}")
