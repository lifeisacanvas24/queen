# ============================================================
# quant/patterns/composite.py
# ============================================================
# Multi-candle pattern detector — Morning Star, Harami, Piercing Line, etc.
# Polars-native, built for high-speed, streaming-compatible analysis.
# ============================================================

import polars as pl


def detect_composite_patterns(df: pl.DataFrame) -> pl.DataFrame:
    """Detects key multi-candle Japanese candlestick patterns (2–3 candles).

    Adds columns:
      - pattern_name (str)
      - pattern_bias ("bullish" | "bearish" | "neutral")
      - confidence (int, 0–100)
      - pattern_group ("composite")

    Supported Patterns:
      🌅 Morning Star (3-candle bullish reversal)
      🌇 Evening Star (3-candle bearish reversal)
      ☯️ Harami (Bullish/Bearish + Cross)
      🌤 Piercing Line / Dark Cloud Cover
      🕊 Three White Soldiers / Three Black Crows
      ✂️ Tweezers Top / Bottom
    """
    # Helper ratios and previous candles
    df = df.with_columns([
        pl.col("close").shift(1).alias("prev_close"),
        pl.col("open").shift(1).alias("prev_open"),
        pl.col("close").shift(2).alias("prev2_close"),
        pl.col("open").shift(2).alias("prev2_open"),
    ])

    # Basic conditions
    is_bullish = pl.col("close") > pl.col("open")
    is_bearish = pl.col("close") < pl.col("open")
    prev_bullish = pl.col("prev_close") > pl.col("prev_open")
    prev_bearish = pl.col("prev_close") < pl.col("prev_open")

    # === 🌅 Morning Star ===
    morning_star = (
        prev_bearish &
        (pl.col("open").shift(1) < pl.col("prev_close")) &  # small-bodied middle candle
        is_bullish &
        (pl.col("close") > pl.col("prev2_open"))  # strong bullish close
    )

    # === 🌇 Evening Star ===
    evening_star = (
        prev_bullish &
        (pl.col("open").shift(1) > pl.col("prev_close")) &
        is_bearish &
        (pl.col("close") < pl.col("prev2_open"))
    )

    # === ☯️ Harami (Bullish & Bearish) ===
    bullish_harami = (
        prev_bearish &
        is_bullish &
        (pl.col("open") > pl.col("prev_close")) &
        (pl.col("close") < pl.col("prev_open"))
    )

    bearish_harami = (
        prev_bullish &
        is_bearish &
        (pl.col("open") < pl.col("prev_close")) &
        (pl.col("close") > pl.col("prev_open"))
    )

    # === ☯️ Harami Cross ===
    harami_cross = (
        ((pl.col("close") - pl.col("open")).abs() < (pl.col("open") * 0.001)) &
        ((pl.col("prev_close") - pl.col("prev_open")).abs() > (pl.col("open") * 0.01))
    )

    # === 🌤 Piercing Line (Bullish) ===
    piercing_line = (
        prev_bearish &
        is_bullish &
        (pl.col("open") < pl.col("prev_close")) &
        (pl.col("close") > ((pl.col("prev_open") + pl.col("prev_close")) / 2))
    )

    # === 🌑 Dark Cloud Cover (Bearish) ===
    dark_cloud_cover = (
        prev_bullish &
        is_bearish &
        (pl.col("open") > pl.col("prev_close")) &
        (pl.col("close") < ((pl.col("prev_open") + pl.col("prev_close")) / 2))
    )

    # === 🕊 Three White Soldiers (Bullish) ===
    three_white_soldiers = (
        (pl.col("close") > pl.col("open")) &
        (pl.col("close").shift(1) > pl.col("open").shift(1)) &
        (pl.col("close").shift(2) > pl.col("open").shift(2)) &
        (pl.col("close") > pl.col("close").shift(1)) &
        (pl.col("close").shift(1) > pl.col("close").shift(2))
    )

    # === 🕊 Three Black Crows (Bearish) ===
    three_black_crows = (
        (pl.col("close") < pl.col("open")) &
        (pl.col("close").shift(1) < pl.col("open").shift(1)) &
        (pl.col("close").shift(2) < pl.col("open").shift(2)) &
        (pl.col("close") < pl.col("close").shift(1)) &
        (pl.col("close").shift(1) < pl.col("close").shift(2))
    )

    # === ✂️ Tweezers Top / Bottom ===
    tweezers_top = (
        prev_bullish &
        is_bearish &
        ((pl.col("high") - pl.col("high").shift(1)).abs() < (pl.col("high") * 0.001))
    )

    tweezers_bottom = (
        prev_bearish &
        is_bullish &
        ((pl.col("low") - pl.col("low").shift(1)).abs() < (pl.col("low") * 0.001))
    )

    # === Confidence levels ===
    df = df.with_columns([
        pl.when(morning_star | evening_star).then(pl.lit(90))
        .when(three_white_soldiers | three_black_crows).then(pl.lit(95))
        .when(bullish_harami | bearish_harami | harami_cross).then(pl.lit(80))
        .when(piercing_line | dark_cloud_cover).then(pl.lit(85))
        .when(tweezers_top | tweezers_bottom).then(pl.lit(75))
        .otherwise(0)
        .alias("confidence")
    ])

    # === Pattern name + bias ===
    df = df.with_columns([
        pl.when(morning_star).then(pl.lit("Morning Star"))
        .when(evening_star).then(pl.lit("Evening Star"))
        .when(bullish_harami).then(pl.lit("Bullish Harami"))
        .when(bearish_harami).then(pl.lit("Bearish Harami"))
        .when(harami_cross).then(pl.lit("Harami Cross"))
        .when(piercing_line).then(pl.lit("Piercing Line"))
        .when(dark_cloud_cover).then(pl.lit("Dark Cloud Cover"))
        .when(three_white_soldiers).then(pl.lit("Three White Soldiers"))
        .when(three_black_crows).then(pl.lit("Three Black Crows"))
        .when(tweezers_top).then(pl.lit("Tweezers Top"))
        .when(tweezers_bottom).then(pl.lit("Tweezers Bottom"))
        .otherwise(pl.lit(None))
        .alias("pattern_name"),

        pl.when(
            morning_star | bullish_harami | harami_cross |
            piercing_line | three_white_soldiers | tweezers_bottom
        ).then(pl.lit("bullish"))
        .when(
            evening_star | bearish_harami | dark_cloud_cover |
            three_black_crows | tweezers_top
        ).then(pl.lit("bearish"))
        .otherwise(pl.lit("neutral"))
        .alias("pattern_bias"),

        pl.lit("composite").alias("pattern_group")
    ])

    return df
