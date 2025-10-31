from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.absorption import (
    detect_absorption_zones,
    summarize_absorption,
)


def _build_mock(n: int = 200) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    cmv = np.sin(np.linspace(0, 6, n)) * 0.08 + rng.normal(0, 0.01, n)
    vol = rng.integers(1000, 5000, n)
    chaikin = rng.normal(0, 400, n)
    chaikin[80:95] += 1200  # brief positive surge
    mfi = np.clip(50 + rng.normal(0, 8, n).cumsum() / 20, 0, 100)

    return pl.DataFrame(
        {
            "CMV": cmv,
            "volume": vol,
            "Chaikin_Osc": chaikin,
            "MFI": mfi,
        }
    )


def test():
    df = _build_mock(220)
    out = detect_absorption_zones(df)

    # columns present
    for c in ("Absorption_Score", "Absorption_Flag", "Absorption_Zone"):
        assert c in out.columns, f"missing {c}"

    # score bounded
    sc = out["Absorption_Score"]
    assert (
        float(sc.min()) >= -1.0 - 1e-9 and float(sc.max()) <= 1.0 + 1e-9
    ), "score out of bounds"

    # summary contains the expected keys
    summary = summarize_absorption(out)
    assert (
        "Accumulations:" in summary and "Distributions:" in summary
    ), "summary missing fields"

    print("Summary:", summary)
    print("✅ smoke_absorption: passed")


if __name__ == "__main__":
    test()
