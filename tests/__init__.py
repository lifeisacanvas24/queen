#!/usr/bin/env python3
# ============================================================
# queen/tests/__init__.py — v1.1 (One-Command Smoke Test Bundle)
# ============================================================
"""Run all smoke tests sequentially via `python -m queen.tests`.

This aggregates lightweight sanity checks for helpers, IO, instruments,
and market-time logic, ensuring basic functional integrity without pytest.
"""

from __future__ import annotations

import importlib
import sys
import textwrap

# ------------------------------------------------------------
# Ordered test modules (CLI-friendly)
# ------------------------------------------------------------
SMOKES = [
    "queen.tests.smoke_io",
    "queen.tests.smoke_instruments",
    "queen.tests.smoke_fetch_utils",
    "queen.tests.smoke_market_time",
    "queen.tests.smoke_market_sleep",
    "queen.tests.smoke_intervals",
    "queen.tests.smoke_schema_adapter",   # ← new
    "queen.tests.smoke_rate_limiter",     # ← new
]

# ------------------------------------------------------------
# Runner
# ------------------------------------------------------------
def run_all() -> int:
    banner = textwrap.dedent(
        """
        🧪 Queen Test Suite — Sequential Run
        ------------------------------------------------------------
        """
    )
    print(banner.strip())
    failed: list[str] = []

    for name in SMOKES:
        print(f"\n▶ Running {name} ...")
        try:
            mod = importlib.import_module(name)
            # prefer run_all() > main() > __main__()
            if hasattr(mod, "run_all"):
                mod.run_all()
            elif hasattr(mod, "main"):
                mod.main()
            elif hasattr(mod, "__main__"):
                mod.__main__()
            else:
                print(f"ℹ️  {name} has no callable entry; assumed ok.")
            print(f"✅ {name}: passed")
        except Exception as e:
            print(f"❌ {name}: {e}")
            failed.append(name)

    print("\n" + "—" * 60)
    if failed:
        print(f"❌ {len(failed)} failed → {', '.join(failed)}")
        code = 1
    else:
        print("✅ All smokes passed.")
        code = 0

    # allow non-fatal behavior inside IDEs
    if __name__ == "__main__":
        sys.exit(code)
    return code


if __name__ == "__main__":
    run_all()
