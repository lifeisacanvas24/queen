#!/usr/bin/env python3
from queen.technicals.signals.registry import (
    build_registry,
    names,
    names_with_modules,
    reset_registry,
)


def test_registry_build():
    reset_registry()
    reg = build_registry()
    assert isinstance(reg, dict)
    _ = names()
    _ = names_with_modules()


if __name__ == "__main__":
    test_registry_build()
    print("✅ smoke_registry: all checks passed")
