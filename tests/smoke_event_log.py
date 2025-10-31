from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.event_log import log_tactical_events

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None


def test():
    dummy = {
        "5m": pl.DataFrame(
            {
                "CMV": np.random.randn(8),
                "CMV_Bias": ["🟢"] * 8,
                "Regime_Emoji": ["🟢 Trend"] * 8,
                "Reversal_Alert": ["➡️ Stable"] * 8,
                "Reversal_Score": np.random.uniform(0, 4, 8),
                "SPS": np.random.uniform(0.2, 0.9, 8),
                "volume": np.random.randint(2_000, 6_000, 8),
            }
        ),
        "15m": pl.DataFrame(
            {
                "CMV": np.random.randn(5),
                "CMV_Bias": ["🔻"] * 5,
                "Regime_Emoji": ["⚫ Neutral"] * 5,
                "Reversal_Alert": ["➡️ Stable"] * 5,
                "Reversal_Score": np.random.uniform(0, 4, 5),
                "SPS": np.random.uniform(0.2, 0.9, 5),
                "volume": np.random.randint(2_000, 6_000, 5),
            }
        ),
    }

    out = log_tactical_events(dummy)
    assert not out.is_empty()
    if SETTINGS:
        log_path = SETTINGS.PATHS["LOGS"] / "tactical_event_log.csv"
    else:
        log_path = Path("queen/data/runtime/logs/tactical_event_log.csv")
    assert log_path.exists(), "Log file not created"
    print("✅ smoke_event_log: passed")


if __name__ == "__main__":
    test()
