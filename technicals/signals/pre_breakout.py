# queen/technicals/signals/pre_breakout.py
# ------------------------------------------------------------
# Setup Pressure Scoring (SPS): CPR-like width + volume/momentum blend
# Pure, config-free. Reuses advanced indicators if present; else safe fallback.
# ------------------------------------------------------------
from __future__ import annotations

import polars as pl


def _ensure_bollinger(
    df: pl.DataFrame, period: int = 20, col: str = "close"
) -> pl.DataFrame:
    need = {"bb_mid", "bb_upper", "bb_lower"}
    if need.issubset(df.columns):
        return df

    # Try to reuse advanced.bollinger_bands if available
    try:
        from queen.technicals.indicators.advanced import bollinger_bands  # type: ignore

        mid, up, lo = bollinger_bands(df, period=period, stddev=2.0, column=col)
        return df.with_columns(
            [mid.alias("bb_mid"), up.alias("bb_upper"), lo.alias("bb_lower")]
        )
    except Exception:
        pass

    # Safe inline fallback (Series-native)
    mid = df[col].rolling_mean(window_size=period)
    std = df[col].rolling_std(window_size=period)
    up = mid + 2.0 * std
    lo = mid - 2.0 * std
    return df.with_columns(
        [mid.alias("bb_mid"), up.alias("bb_upper"), lo.alias("bb_lower")]
    )


def compute_pre_breakout(
    df: pl.DataFrame, timeframe: str = "intraday_15m"
) -> pl.DataFrame:
    """Compute CPR width & SPS with minimal assumptions.
    Returns DF with: cpr_width, SPS, momentum, momentum_smooth, trend_up
    """
    if not {"close", "high", "low", "volume"}.issubset(df.columns):
        raise ValueError("compute_pre_breakout: requires close/high/low/volume")

    out = _ensure_bollinger(df)

    # CPR-like width (% of mid) — guard divide-by-zero
    out = out.with_columns(
        (
            (pl.col("bb_upper") - pl.col("bb_lower")) / (pl.col("bb_mid").abs() + 1e-9)
        ).alias("cpr_width")
    )

    # If a Volume Pressure Ratio exists upstream, use it; else neutral 1.0
    if "VPR" not in out.columns:
        out = out.with_columns(pl.lit(1.0).alias("VPR"))

    # Simple, monotonic SPS: higher when width is tighter and VPR is higher
    out = out.with_columns((pl.col("VPR") / (1.0 + pl.col("cpr_width"))).alias("SPS"))

    # Momentum context
    out = out.with_columns(
        [
            pl.col("close").diff().alias("momentum"),
            pl.col("close").diff().rolling_mean(window_size=5).alias("momentum_smooth"),
        ]
    ).with_columns((pl.col("momentum_smooth") > 0).cast(pl.Int8).alias("trend_up"))

    return out.fill_nan(None).fill_null(strategy="forward")
