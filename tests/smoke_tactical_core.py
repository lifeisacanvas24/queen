from __future__ import annotations

import polars as pl
from queen.technicals.signals.tactical.core import compute_tactical_index


def test():
    # dict path
    metrics = {"RScore_norm": 0.62, "VolX_norm": 0.35, "LBX_norm": 0.48}
    out = compute_tactical_index(metrics, interval="15m")
    assert "Tactical_Index" in out or "regime" in out
    print("Tactical (dict):", out)

    # df path
    df = pl.DataFrame(metrics)
    out2 = compute_tactical_index(df, interval="1h")
    assert "regime" in out2
    print("Tactical (df):", out2)


if __name__ == "__main__":
    test()
    print("✅ smoke_tactical_core: passed")
