#!/usr/bin/env python3
# ============================================================
# queen/technicals/volume_strength_intraday.py — v1.1
# ------------------------------------------------------------
# Intraday Volume Strength (15m-compressed, Polars-only)
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import polars as pl

from queen.helpers.market import MARKET_TZ_KEY


def _to_15m_volume_bars(df: pl.DataFrame) -> pl.DataFrame:
    """Compress arbitrary intraday OHLCV into 15m volume bars."""
    if df.is_empty() or "timestamp" not in df.columns or "volume" not in df.columns:
        return pl.DataFrame(
            {
                "ts15": pl.Series([], dtype=pl.Datetime),
                "volume": pl.Series([], dtype=pl.Float64),
            }
        )

    work = df.with_columns(
        pl.col("timestamp")
        .dt.convert_time_zone(MARKET_TZ_KEY)
        .alias("ts15")
    )

    out = (
        work.sort("ts15")
        .group_by_dynamic(
            "ts15",
            every="15m",
            period="15m",
            closed="right",
            label="right",
        )
        .agg(
            pl.col("volume").sum().cast(pl.Float64).alias("volume"),
        )
        .sort("ts15")
    )

    return out


def _percentile_rank(series: pl.Series, value: float) -> float:
    """Return percentile rank (0–100) of `value` within `series`."""
    if series.is_empty():
        return 0.0
    try:
        arr = series.drop_nulls().sort()
        if arr.is_empty():
            return 0.0
        leq = int((arr <= value).sum())
        n = max(1, arr.len())
        return float(leq) / float(n) * 100.0
    except Exception:
        return 0.0


def _label_from_ratio(ratio: float) -> str:
    """Map last/avg20 ratio to a human label."""
    if ratio <= 0:
        return "Unknown"
    if ratio < 0.6:
        return "Dry"
    if ratio < 1.0:
        return "Below Avg"
    if ratio < 1.5:
        return "Normal"
    if ratio < 2.0:
        return "Strong"
    if ratio < 3.0:
        return "Very Strong"
    return "Extreme"


def _score_from_ratio_and_rank(ratio: float, pct_rank: float) -> float:
    """Combine ratio + percentile into a 0–10 score."""
    if ratio <= 0 or pct_rank <= 0:
        return 0.0

    if ratio < 0.6:
        base = 1.0
    elif ratio < 1.0:
        base = 2.0
    elif ratio < 1.5:
        base = 4.0
    elif ratio < 2.0:
        base = 6.0
    elif ratio < 3.0:
        base = 8.0
    else:
        base = 9.0

    if pct_rank >= 95:
        bonus = 3.0
    elif pct_rank >= 80:
        bonus = 2.0
    elif pct_rank >= 60:
        bonus = 1.0
    else:
        bonus = 0.0

    return float(min(10.0, base + bonus))


def compute_intraday_volume_strength(
    df: pl.DataFrame,
    *,
    min_bars: int = 30,
    lookback_bars: int = 60,
    avg_window: int = 20,
) -> Dict[str, Any]:
    """Compute intraday volume strength on 15m-compressed bars."""
    neutral: Dict[str, Any] = {
        "Vol_Strength_Score_I": 0.0,
        "Vol_Strength_Label_I": "Unknown",
        "Vol_Strength_Ratio_I": 0.0,
        "Vol_Last_I": 0.0,
        "Vol_Avg20_I": 0.0,
        "Vol_PctRank_I": 0.0,
        "Vol_Bars_I": 0,
    }

    try:
        bars15 = _to_15m_volume_bars(df)
    except Exception:
        return neutral

    if bars15.is_empty() or "volume" not in bars15.columns:
        return neutral

    if bars15.height < max(min_bars, avg_window + 1):
        out = dict(neutral)
        out["Vol_Bars_I"] = int(bars15.height)
        out["Vol_Strength_Label_I"] = "Insufficient"
        return out

    vol = bars15["volume"].cast(pl.Float64, strict=False)
    vol_non_null = vol.drop_nulls()

    if vol_non_null.is_empty():
        return neutral

    last_vol = float(vol_non_null.tail(1).item())

    lb = int(min(lookback_bars, vol_non_null.len()))
    tail = vol_non_null.tail(lb)

    if tail.len() < avg_window:
        avg20 = float(tail.mean() or 0.0)
    else:
        avg20 = float(tail.tail(avg_window).mean() or 0.0)

    if avg20 <= 0:
        ratio = 0.0
    else:
        ratio = float(last_vol) / float(avg20)

    pct_rank = _percentile_rank(tail, last_vol)
    label = _label_from_ratio(ratio)
    score = _score_from_ratio_and_rank(ratio, pct_rank)

    return {
        "Vol_Strength_Score_I": float(round(score, 2)),
        "Vol_Strength_Label_I": label,
        "Vol_Strength_Ratio_I": float(round(ratio, 3)),
        "Vol_Last_I": float(round(last_vol, 1)),
        "Vol_Avg20_I": float(round(avg20, 1)),
        "Vol_PctRank_I": float(round(pct_rank, 1)),
        "Vol_Bars_I": int(bars15.height),
    }
