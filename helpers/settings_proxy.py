#!/usr/bin/env python3
# ============================================================
# queen/helpers/settings_proxy.py — Read-only Dot-Access Layer (v1.1)
# ============================================================
"""Settings Proxy
-----------------
Read-only, dot-access wrapper over the actual settings registry,
assembled from multiple modules (no single global dict).
"""

from __future__ import annotations

from typing import Any, Dict

# Canonical sources
from queen.settings import settings as S


# ------------------------------------------------------------
# 🧱 DotDict — recursive dot-access wrapper
# ------------------------------------------------------------
class DotDict:
    __slots__ = ("_data",)

    def __init__(self, data: Any):
        if isinstance(data, dict):
            self._data = {k: DotDict(v) for k, v in data.items()}
        else:
            self._data = data

    def __getattr__(self, name: str) -> Any:
        if isinstance(self._data, dict) and name in self._data:
            return self._data[name]
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __getitem__(self, key: str) -> Any:
        if isinstance(self._data, dict):
            return self._data[key]
        raise TypeError(f"Cannot index non-dict object: {type(self._data).__name__}")

    def __repr__(self) -> str:
        return f"<DotDict {self._data!r}>"

    def __iter__(self):
        if isinstance(self._data, dict):
            return iter(self._data)
        raise TypeError("DotDict object is not iterable")

    def items(self):
        if isinstance(self._data, dict):
            return self._data.items()
        raise TypeError("DotDict has no items() for non-dict data")

    def as_dict(self) -> Dict[str, Any]:
        if isinstance(self._data, dict):
            return {
                k: (v.as_dict() if isinstance(v, DotDict) else v)
                for k, v in self._data.items()
            }
        return self._data

    # immutable
    def __setattr__(self, key, value):
        if key == "_data":
            super().__setattr__(key, value)
        else:
            raise AttributeError("DotDict is read-only")

    def __setitem__(self, key, value):
        raise TypeError("DotDict is read-only")

    def __delitem__(self, key):
        raise TypeError("DotDict is read-only")


# ------------------------------------------------------------
# 🗄️ Assemble a forward-only registry (no back-compat)
# ------------------------------------------------------------
REGISTRY: Dict[str, Any] = {
    "app": S.APP,
    "paths": S.PATHS,
    "defaults": S.DEFAULTS,
    "exchange": S.EXCHANGE,
    "logging": S.LOGGING,
    "diagnostics": S.DIAGNOSTICS,
    "brokers": S.BROKERS,
    "alerts": S.DEFAULTS.get("ALERTS", {}),
    "colors": S.DEFAULTS.get("CONSOLE_COLORS", {}),
    "sinks": {
        "alert_paths": {
            "jsonl": S.alert_path_jsonl(),
            "sqlite": S.alert_path_sqlite(),
            "rules": S.alert_path_rules(),
            "state": S.alert_path_state(),
        },
    },
}

# Public, read-only proxy
SETTINGS = DotDict(REGISTRY)

# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🧩 Settings Proxy Test")
    print("APP Name:", SETTINGS.app.NAME)
    print("Default Broker:", SETTINGS.defaults.BROKER)
    print("NSE Open Time:", SETTINGS.exchange.EXCHANGES.NSE_BSE.MARKET_HOURS.OPEN)
