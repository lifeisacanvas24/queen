# queen/tests/smoke_tactical_index_modes.py
from __future__ import annotations

import polars as pl
from queen.technicals.signals.tactical.core import compute_tactical_index


def test():
    # dict mode
    d = {
        "RScore_norm": 0.7,
        "VolX_norm": 0.4,
        "LBX_norm": 0.6,
    }  # or “RScore/VolX/LBX” if your config maps “source”
    out_d = compute_tactical_index(d, interval="15m")
    assert "regime" in out_d and "Tactical_Index" in out_d

    # DF mode
    df = pl.DataFrame(
        {"RScore_norm": [0.5, 0.6], "VolX_norm": [0.3, 0.5], "LBX_norm": [0.7, 0.4]}
    )
    out_df = compute_tactical_index(df, interval="1h")
    assert "regime" in out_df and "Tactical_Index" in out_df

    print("✅ smoke_tactical_index_modes: passed")


if __name__ == "__main__":
    test()
