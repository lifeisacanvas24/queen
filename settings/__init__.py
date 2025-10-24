#!/usr/bin/env python3
# ============================================================
# queen/settings/__init__.py — Central Config Registry (v2.0)
# ============================================================
"""Unified import hub for all Queen of Quant configuration modules.

Provides:
  • `settings`  — dot-accessible namespace (preferred)
  • `SETTINGS`  — legacy dict registry (back-compat)
  • helper passthroughs: get_env(), set_env(), etc.
"""

from __future__ import annotations

from types import SimpleNamespace

# ---- Pull the canonical symbols from settings.py -----------------------------
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
    broker_config,
    get_env,
    get_env_paths,
    log_file,
    market_hours,
    resolve_log_path,
    set_env,
)

# ---- Optional tactical/analytics configs ------------------------------------
try:
    from .metrics import METRICS
except Exception:
    METRICS = {}

try:
    from .profiles import PROFILES
except Exception:
    PROFILES = {}

try:
    from .regimes import REGIMES, derive_regime, get_regime_config
except Exception:
    REGIMES = {}

    def derive_regime(*_a, **_k):  # noqa: D401
        """stub"""
        return None

    def get_regime_config(*_a, **_k):  # noqa: D401
        """stub"""
        return None


try:
    from .tactical import TACTICAL
except Exception:
    TACTICAL = {}

try:
    from .timeframes import TIMEFRAMES
except Exception:
    TIMEFRAMES = {}

try:
    from .weights import WEIGHTS
except Exception:
    WEIGHTS = {}


# ---- Dot-accessible namespace (preferred) -----------------------------------
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
)

# ---- Legacy dict-style registry (still supported) ---------------------------
SETTINGS = settings.as_dict()


# ---- Convenience passthroughs ------------------------------------------------
def get(section: str):
    """Quick access to any config section (case-insensitive)."""
    d = SETTINGS
    return d.get(section.lower()) or d.get(section.upper())


def list_sections():
    """List all available config sections."""
    return sorted(SETTINGS.keys())


__all__ = [
    "settings",
    "SETTINGS",
    "get",
    "list_sections",
    # helpers
    "get_env",
    "set_env",
    "market_hours",
    "broker_config",
    "log_file",
    "resolve_log_path",
    "get_env_paths",
]
