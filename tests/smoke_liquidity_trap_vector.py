# queen/tests/smoke_liquidity_trap_vector.py
import numpy as np
import polars as pl
from queen.technicals.signals.tactical.tactical_liquidity_trap import (
    detect_liquidity_trap,
)


def test():
    n = 40
    df = pl.DataFrame(
        {
            "CMV": np.sin(np.linspace(0, 5, n)),
            "SPS": np.linspace(0.9, 0.7, n),  # peak then cool-off
            "MFI": np.linspace(60, 35, n),  # falling
            "Chaikin_Osc": [-0.2] * n,  # negative (bear absorption)
        }
    )
    out = detect_liquidity_trap(df, threshold_sps=0.85, lookback=5)
    assert {"Liquidity_Trap", "Liquidity_Trap_Score"} <= set(out.columns)
    print("✅ smoke_liquidity_trap_vector: passed")


if __name__ == "__main__":
    test()
