# queen/helpers/__init__.py
"""Lightweight helpers package init (lazy submodule access).

Usage:
    from queen.helpers import io
    io.append_jsonl(...)

    # When (and only when) you actually need them:
    from queen.helpers import market, instruments, logger, pl_compat
"""

from importlib import import_module as _im

__all__ = ["io", "logger", "pl_compat", "market", "instruments"]


def __getattr__(name: str):
    if name in __all__:
        return _im(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
