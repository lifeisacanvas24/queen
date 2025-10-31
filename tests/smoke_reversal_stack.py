# queen/tests/smoke_reversal_stack.py
import polars as pl
from queen.technicals.signals.tactical.reversal_stack import compute_reversal_stack


def test():
    df = pl.DataFrame(
        {
            "Regime_State": ["TREND", "VOLATILE"],
            "Divergence_Signal": ["Bullish Divergence", ""],
            "Squeeze_Signal": ["Squeeze Release", ""],
            "Liquidity_Trap": ["Bear Trap", ""],
            "Exhaustion_Signal": ["🟩 Bullish Exhaustion", ""],
        }
    )
    out = compute_reversal_stack(df)
    assert {"Reversal_Score", "Reversal_Stack_Alert"} <= set(out.columns)
    print("✅ smoke_reversal_stack: passed")


if __name__ == "__main__":
    test()
