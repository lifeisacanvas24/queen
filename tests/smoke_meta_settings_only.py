# queen/tests/smoke_meta_settings_only.py
from __future__ import annotations

import polars as pl
from queen.technicals.signals.tactical.meta_controller import meta_controller_run
from queen.technicals.signals.tactical.meta_introspector import run_meta_introspector


def test():
    cfg = meta_controller_run()
    assert "retrain_interval_hours" in cfg
    out = run_meta_introspector()
    assert (out is None) or isinstance(out, pl.DataFrame)
    print("✅ smoke_meta_settings_only: passed")


if __name__ == "__main__":
    test()
