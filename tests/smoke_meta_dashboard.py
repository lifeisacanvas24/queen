# queen/tests/smoke_meta_dashboard.py
from __future__ import annotations

from queen.technicals.signals.tactical.meta_dashboard import render_meta_dashboard


def test():
    render_meta_dashboard()
    print("✅ smoke_meta_dashboard: rendered")


if __name__ == "__main__":
    test()
