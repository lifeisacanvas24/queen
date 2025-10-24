#!/usr/bin/env python3
# ============================================================
# queen/helpers/settings_proxy.py — Read-only Dot-Access Layer
# ============================================================
"""Settings Proxy (v1.0)
---------------------
Provides a recursive dot-access interface to the global Queen of Quant
configuration registry (`queen.settings.SETTINGS`).

🧠 Why
    - Syntactic sugar: access nested configs via dot-notation
    - Immutable by design (read-only)
    - Ideal for interactive daemons, notebooks, and CLI tools

Example:
-------
    >>> from queen.helpers.settings_proxy import SETTINGS
    >>> SETTINGS.exchange.EXCHANGES.NSE_BSE.MARKET_HOURS.OPEN
    '09:15'
    >>> SETTINGS.brokers.UPSTOX.RATE_LIMITS.PER_SECOND
    50

"""

from __future__ import annotations

from typing import Any, Dict

# Import the canonical registry
from queen.settings import SETTINGS as _SETTINGS


# ------------------------------------------------------------
# 🧱 DotDict — recursive dot-access wrapper
# ------------------------------------------------------------
class DotDict:
    """A recursive read-only mapping that allows attribute-style access.

    Example:
        data = DotDict({"A": {"B": {"C": 42}}})
        print(data.A.B.C)  # 42

    """

    __slots__ = ("_data",)

    def __init__(self, data: Any):
        if isinstance(data, dict):
            # Recursively wrap nested dicts
            self._data = {k: DotDict(v) for k, v in data.items()}
        else:
            self._data = data

    # Attribute-style access
    def __getattr__(self, name: str) -> Any:
        if isinstance(self._data, dict) and name in self._data:
            return self._data[name]
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    # Dict-style access
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
        """Convert back to a normal dict (recursively)."""
        if isinstance(self._data, dict):
            return {
                k: (v.as_dict() if isinstance(v, DotDict) else v)
                for k, v in self._data.items()
            }
        return self._data

    # Immutable
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
# ⚙️ Create the Read-Only Global Proxy
# ------------------------------------------------------------
SETTINGS = DotDict(_SETTINGS)


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🧩 Settings Proxy Test")
    print("APP Name:", SETTINGS.app.NAME)
    print("Default Broker:", SETTINGS.defaults.BROKER)
    print("NSE Open Time:", SETTINGS.exchange.EXCHANGES.NSE_BSE.MARKET_HOURS.OPEN)
    print("Regime States:", list(SETTINGS.regimes.keys()))
