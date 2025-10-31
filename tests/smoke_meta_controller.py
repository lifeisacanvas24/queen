# queen/tests/smoke_meta_controller.py
from __future__ import annotations

from queen.technicals.signals.tactical.meta_controller import meta_controller_run


def test():
    cfg = meta_controller_run()
    assert isinstance(cfg, dict)
    print("✅ smoke_meta_controller: passed")


if __name__ == "__main__":
    test()
