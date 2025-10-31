from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.ai_inference import run_ai_inference


def test():
    n = 50
    df = pl.DataFrame(
        {
            "CMV": np.random.uniform(-1, 1, n),
            "Reversal_Score": np.random.uniform(0, 5, n),
            "Confidence": np.random.uniform(0.5, 1.0, n),
            "ATR_Ratio": np.random.uniform(0.8, 1.4, n),
            "BUY_Ratio": np.random.uniform(0, 1, n),
            "SELL_Ratio": np.random.uniform(0, 1, n),
        }
    )
    out = run_ai_inference({"15m": df, "1h": df}, model_path="__missing__.pkl")
    assert {"timeframe", "BUY_Prob", "SELL_Prob", "Forecast"}.issubset(out.columns)


if __name__ == "__main__":
    test()
    print("✅ smoke_ai_inference: passed")
