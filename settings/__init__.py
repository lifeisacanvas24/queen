#!/usr/bin/env python3
# ============================================================
# queen/settings/__init__.py — Central Config Registry (v2.2)
# ============================================================
"""Unified import hub for all Queen of Quant configuration modules.

Provides:
  • `settings`  — dot-accessible namespace (preferred)
  • `SETTINGS`  — dict snapshot (plain mapping)
  • helper passthroughs: get_env(), set_env(), market_hours(), alert_path_*(), etc.
"""

from __future__ import annotations

from types import SimpleNamespace

# Canonical settings module (module object, not exported as SETTINGS to avoid name clash)
from . import settings as settings_mod

# Pull commonly used symbols + helpers straight from settings.py
from .settings import (
    APP,
    BROKERS,
    DEFAULTS,
    DIAGNOSTICS,
    EXCHANGE,
    FETCH,
    LOGGING,
    PATHS,
    SCHEDULER,
    # ✅ alert sinks + helpers
    alert_path_jsonl,
    alert_path_rules,
    alert_path_sqlite,
    alert_path_state,
    broker_config,
    get_env,
    get_env_paths,
    log_file,
    market_hours,
    resolve_log_path,
    set_env,
)

# Add these timeframe helpers to the import list
from .timeframes import (
    TIMEFRAME_MAP,  # if you have it; else omit
    is_intraday,
    normalize_tf,
    parse_tf,
    tf_to_minutes,
    to_fetcher_interval,
    validate_token,  # NEW helper we’ll add below
    window_days_for_tf,  # NEW helper we’ll add below
)

# Optional tactical/analytics configs (tolerate absence)
try:
    from .metrics import METRICS  # type: ignore
except Exception:
    METRICS = {}

try:
    from .profiles import PROFILES  # type: ignore
except Exception:
    PROFILES = {}

try:
    from .regimes import REGIMES, derive_regime, get_regime_config  # type: ignore
except Exception:
    REGIMES = {}

    def derive_regime(*_a, **_k):  # stub
        return

    def get_regime_config(*_a, **_k):  # stub
        return


try:
    from .tactical import TACTICAL  # type: ignore
except Exception:
    TACTICAL = {}

try:
    from .timeframes import TIMEFRAMES  # type: ignore
except Exception:
    TIMEFRAMES = {}

try:
    # If your weights module exposes a dict named TIMEFRAMES; otherwise adapt to your schema.
    from .weights import TIMEFRAMES as WEIGHTS  # type: ignore
except Exception:
    WEIGHTS = {}


class _Settings(SimpleNamespace):
    """Dot-accessible view + a dict() snapshot when needed."""

    def as_dict(self):
        return {
            "app": self.APP,
            "paths": self.PATHS,
            "brokers": self.BROKERS,
            "exchange": self.EXCHANGE,
            "fetch": self.FETCH,
            "scheduler": self.SCHEDULER,
            "diagnostics": self.DIAGNOSTICS,
            "logging": self.LOGGING,
            "defaults": self.DEFAULTS,
            "metrics": self.METRICS,
            "tactical": self.TACTICAL,
            "weights": self.WEIGHTS,
            "profiles": self.PROFILES,
            "timeframes": self.TIMEFRAMES,
            "regimes": self.REGIMES,
            "env": self.get_env(),
        }


settings = _Settings(
    APP=APP,
    PATHS=PATHS,
    BROKERS=BROKERS,
    EXCHANGE=EXCHANGE,
    FETCH=FETCH,
    SCHEDULER=SCHEDULER,
    DIAGNOSTICS=DIAGNOSTICS,
    LOGGING=LOGGING,
    DEFAULTS=DEFAULTS,
    METRICS=METRICS,
    TACTICAL=TACTICAL,
    WEIGHTS=WEIGHTS,
    PROFILES=PROFILES,
    TIMEFRAMES=TIMEFRAMES,
    REGIMES=REGIMES,
    # helpers
    get_env=get_env,
    set_env=set_env,
    market_hours=market_hours,
    broker_config=broker_config,
    log_file=log_file,
    resolve_log_path=resolve_log_path,
    get_env_paths=get_env_paths,
    # ✅ alert sinks (so `settings.alert_path_jsonl()` works)
    alert_path_jsonl=alert_path_jsonl,
    alert_path_sqlite=alert_path_sqlite,
    alert_path_rules=alert_path_rules,
    alert_path_state=alert_path_state,
    parse_tf=parse_tf,
    to_fetcher_interval=to_fetcher_interval,
    tf_to_minutes=tf_to_minutes,
    is_intraday=is_intraday,
    normalize_tf=normalize_tf,
    window_days_for_tf=window_days_for_tf,
    validate_token=validate_token,
)

# Plain dict snapshot for callers that prefer a mapping
SETTINGS = settings.as_dict()


def get(section: str):
    """Case-insensitive access to a top-level section from the dict snapshot."""
    d = SETTINGS
    return d.get(section.lower()) or d.get(section.upper())


def list_sections():
    return sorted(SETTINGS.keys())


__all__ = [
    "settings",
    "SETTINGS",
    "get",
    "list_sections",
    # helpers passthrough
    "get_env",
    "set_env",
    "market_hours",
    "broker_config",
    "log_file",
    "resolve_log_path",
    "get_env_paths",
    # ✅ alert-path helpers
    "alert_path_jsonl",
    "alert_path_sqlite",
    "alert_path_rules",
    "alert_path_state",
    "parse_tf",
    "to_fetcher_interval",
    "tf_to_minutes",
    "is_intraday",
    "normalize_tf",
    "window_days_for_tf",
    "validate_token",
]
