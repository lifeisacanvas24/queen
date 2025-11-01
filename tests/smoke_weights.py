#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_weights.py
# ============================================================
from __future__ import annotations

from queen.settings import weights as W


def test():
    sums = W.validate_weights(strict=False)
    assert sums, "empty weights"

    fw = W.fusion_weights_for(["intraday_15m", "hourly_1h", "daily"])
    assert abs(sum(fw.values()) - 1.0) < 1e-9

    g = W.get_thresholds()
    assert 0 < g["EXIT"] < g["ENTRY"] < 1, f"bad global thresholds: {g}"

    tf = W.get_thresholds("intraday_15m")
    assert {"ENTRY", "EXIT"} <= set(tf), "missing keys"

    print("✅ smoke_weights: passed")


if __name__ == "__main__":
    test()
