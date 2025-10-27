import polars as pl
from queen.technicals.patterns.core import (
    bearish_engulfing,
    bullish_engulfing,
    detect_doji,
    hammer,
    shooting_star,
)

# 1) Bullish engulfing (prev red fully engulfed by current green)
df_be = pl.DataFrame(
    {
        "open": [10.0, 10.0, 9.0],
        "high": [10.5, 10.6, 11.2],
        "low": [9.7, 9.6, 8.9],
        "close": [9.4, 9.7, 10.9],  # row1 red, row2 green that engulfs row1
    }
)
print(
    "bullish_engulfing ->", bullish_engulfing(df_be).to_list()
)  # expect [False, False, True]

# 2) Bearish engulfing (prev green fully engulfed by current red)
df_bea = pl.DataFrame(
    {
        "open": [10.0, 9.5, 11.0],
        "high": [10.6, 10.1, 11.1],
        "low": [9.6, 9.4, 9.2],
        "close": [10.3, 9.9, 9.1],  # row1 green, row2 red that engulfs row1
    }
)
print(
    "bearish_engulfing ->", bearish_engulfing(df_bea).to_list()
)  # expect [False, False, True]

# 3) Hammer (long lower wick, tiny upper)
df_h = pl.DataFrame(
    {
        "open": [10.0, 10.2, 10.0],
        "high": [10.2, 10.4, 10.6],
        "low": [9.9, 9.6, 8.0],
        "close": [10.1, 10.3, 10.5],  # last row: big lower wick, small upper
    }
)
print("hammer ->", hammer(df_h).to_list())  # expect [False, False, True]

# 4) Shooting star (long upper wick, tiny lower)
df_ss = pl.DataFrame(
    {
        "open": [10.0, 10.2, 10.5],
        "high": [10.2, 10.6, 13.0],
        "low": [9.9, 10.0, 9.8],
        "close": [10.1, 10.3, 10.0],  # last row: big upper wick, small lower
    }
)
print("shooting_star ->", shooting_star(df_ss).to_list())  # expect [False, False, True]

# 5) Doji (body tiny vs range)
df_d = pl.DataFrame(
    {
        "open": [10.0, 11.0, 11.00],
        "high": [12.0, 11.6, 12.00],
        "low": [9.5, 10.4, 10.00],
        "close": [9.9, 11.1, 11.05],  # last row: |close-open| small vs (high-low)
    }
)
print(
    "doji ->", detect_doji(df_d, tolerance=0.1).to_list()
)  # expect [False, False, True]
