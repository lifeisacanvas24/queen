"""quant/patterns/core.py
--------------------------------------------------
Core single-candle pattern detectors (Polars-native).

Includes:
    • Bullish Engulfing
    • Bearish Engulfing
    • Doji
    • Hammer / Inverted Hammer
    • Marubozu

Outputs:
    - pattern_name
    - pattern_bias
    - confidence (0–100%)
    - pattern_group = "core"
--------------------------------------------------
"""

import polars as pl


def detect_core_patterns(df: pl.DataFrame) -> pl.DataFrame:
    """Detects major single-candle Japanese patterns using Polars expressions."""
    # ------------------------------
    # 📊 Candle structure components
    # ------------------------------
    body = (pl.col("close") - pl.col("open")).abs()
    upper_wick = pl.col("high") - pl.max_horizontal(pl.col("open"), pl.col("close"))
    lower_wick = pl.min_horizontal(pl.col("open"), pl.col("close")) - pl.col("low")
    full_range = pl.col("high") - pl.col("low")
    body_ratio = (body / full_range).fill_null(0)

    # ------------------------------
    # 🟢 Bullish / 🔴 Bearish Engulfing
    # ------------------------------
    prev_open = pl.col("open").shift(1)
    prev_close = pl.col("close").shift(1)

    is_bullish_engulf = (
        (pl.col("close") > pl.col("open")) &
        (prev_close < prev_open) &
        (pl.col("close") >= prev_open) &
        (pl.col("open") <= prev_close)
    )

    is_bearish_engulf = (
        (pl.col("close") < pl.col("open")) &
        (prev_close > prev_open) &
        (pl.col("open") >= prev_close) &
        (pl.col("close") <= prev_open)
    )

    # ------------------------------
    # ⚖️ Doji (small body, long wicks)
    # ------------------------------
    is_doji = body_ratio < 0.1

    # ------------------------------
    # 🔨 Hammer / Inverted Hammer
    # ------------------------------
    is_hammer = (lower_wick > 2 * body) & (upper_wick < body)
    is_inverted_hammer = (upper_wick > 2 * body) & (lower_wick < body)

    # ------------------------------
    # 🕯️ Marubozu (no wicks)
    # ------------------------------
    is_marubozu = (upper_wick < full_range * 0.05) & (lower_wick < full_range * 0.05)

    # ------------------------------
    # 🧠 Pattern labeling
    # ------------------------------
    pattern_name = (
        pl.when(is_bullish_engulf).then(pl.lit("Bullish Engulfing"))
        .when(is_bearish_engulf).then(pl.lit("Bearish Engulfing"))
        .when(is_doji).then(pl.lit("Doji"))
        .when(is_hammer).then(pl.lit("Hammer"))
        .when(is_inverted_hammer).then(pl.lit("Inverted Hammer"))
        .when(is_marubozu).then(pl.lit("Marubozu"))
        .otherwise(pl.lit(None))
        .alias("pattern_name")
    )

    pattern_bias = (
        pl.when(is_bullish_engulf | is_hammer | is_inverted_hammer)
        .then(pl.lit("Bullish"))
        .when(is_bearish_engulf)
        .then(pl.lit("Bearish"))
        .when(is_doji | is_marubozu)
        .then(pl.lit("Neutral"))
        .otherwise(pl.lit(None))
        .alias("pattern_bias")
    )

    # ------------------------------
    # 🎯 Confidence heuristic (0–100)
    # ------------------------------
    confidence = (
        pl.when(is_bullish_engulf | is_bearish_engulf)
        .then(pl.lit(90))
        .when(is_hammer | is_inverted_hammer)
        .then(pl.lit(80))
        .when(is_doji)
        .then(pl.lit(60))
        .when(is_marubozu)
        .then(pl.lit(70))
        .otherwise(pl.lit(0))
        .alias("confidence")
    )

    # ------------------------------
    # 🧩 Combine all
    # ------------------------------
    return df.with_columns([
        pattern_name,
        pattern_bias,
        confidence,
        pl.lit("core").alias("pattern_group"),
    ])
