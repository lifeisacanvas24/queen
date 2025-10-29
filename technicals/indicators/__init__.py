# queen/technicals/indicators/__init__.py
from __future__ import annotations

import importlib

__version__ = "v1.0"
__registry_mode__ = "settings-driven"

__all__ = [
    "overlays",
    "rsi",
    "momentum_macd",
    "vol_keltner",
    "volume_chaikin",
    "volume_mfi",
    "volatility_fusion",
]


def __getattr__(name: str):
    if name in __all__:
        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"{__name__!r} has no attribute {name!r}")
