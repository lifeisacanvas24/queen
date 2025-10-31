# queen/tests/smoke_squeeze_pulse.py
import numpy as np
import polars as pl
from queen.technicals.signals.tactical.squeeze_pulse import (
    detect_squeeze_pulse,
    summarize_squeeze,
)


def test():
    n = 20
    base = np.linspace(100, 110, n)
    df = pl.DataFrame(
        {
            "bb_upper": base + 2,
            "bb_lower": base - 2,
            "keltner_upper": base + 1.4,
            "keltner_lower": base - 1.4,
        }
    )
    out = detect_squeeze_pulse(df)
    s = summarize_squeeze(out)
    assert "Squeeze Ready" in s or "Releases" in s
    print("✅ smoke_squeeze_pulse: passed")


if __name__ == "__main__":
    test()
