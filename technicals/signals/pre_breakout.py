# ============================================================
# queen/technicals/signals/pre_breakout.py
# ------------------------------------------------------------
# Setup Pressure Scoring (SPS): CPR-like width + volume/momentum blend
# - 100% Polars
# - Settings-driven where available (CPR period/stddev)
# - Safe fallbacks when advanced indicator modules are absent
# - No external configs; uses queen.settings.indicators
# ============================================================

from __future__ import annotations
from typing import Dict, Any

import polars as pl

from queen.helpers.logger import log
from queen.helpers.common import timeframe_key
from queen.settings import indicators as IND  # data-only registry


# ---------- CPR/Bollinger params from settings (if present) ----------
def _boll_params(tf_token: str | None) -> Dict[str, Any]:
    """Derive BB-like params from settings.CPR defaults/contexts, else fallback."""
    block = IND.get_block("CPR") or {}
    ctx = {}
    if tf_token:
        ctx_key = timeframe_key(tf_token)
        ctx = (block.get("contexts", {}) or {}).get(ctx_key, {}) or {}
    # map CPR ideas → BB proxy knobs
    # (pivot_method/ compression_threshold are not needed for width calc,
    #  but keeping compression_threshold as a soft signal threshold if needed)
    period = int(ctx.get("period", 20))  # allow period in CPR if provided
    stddev = float(ctx.get("stddev", 2.0))
    return {"period": period, "stddev": stddev}


# ---------- ensure BB columns (Polars native fallback) ----------
def _ensure_bollinger(
    df: pl.DataFrame, *, period: int, stddev: float, price_col: str = "close"
) -> pl.DataFrame:
    need = {"bb_mid", "bb_upper", "bb_lower"}
    if need.issubset(df.columns):
        return df

    # Attempt to reuse an advanced BB implementation if present (optional)
    try:
        from queen.technicals.indicators.advanced import (  # type: ignore
            bollinger_bands,
        )

        mid, up, lo = bollinger_bands(
            df, period=period, stddev=stddev, column=price_col
        )
        return df.with_columns(
            [mid.alias("bb_mid"), up.alias("bb_upper"), lo.alias("bb_lower")]
        )
    except Exception:
        pass

    # Polars fallback
    mid = pl.col(price_col).rolling_mean(window_size=period)
    std = pl.col(price_col).rolling_std(window_size=period)
    up = mid + stddev * std
    lo = mid - stddev * std
    return df.with_columns(
        [mid.alias("bb_mid"), up.alias("bb_upper"), lo.alias("bb_lower")]
    )


# ---------- public API ----------
def compute_pre_breakout(
    df: pl.DataFrame,
    *,
    timeframe: str = "intraday_15m",
    price_col: str = "close",
    volume_col: str = "volume",
) -> pl.DataFrame:
    """Compute CPR-like width and a simple SPS score.

    Outputs:
      • cpr_width      — (BB_upper - BB_lower) / |BB_mid|
      • VPR            — volume pressure ratio (if absent upstream → 1.0)
      • SPS            — VPR / (1 + cpr_width)
      • momentum       — close.diff()
      • momentum_smooth— rolling mean of momentum (5)
      • trend_up       — 1 if momentum_smooth > 0 else 0
    """
    req = {price_col, "high", "low", volume_col}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"compute_pre_breakout: missing {sorted(missing)}")

    # Params from settings (with safe defaults)
    p = _boll_params(timeframe)

    out = _ensure_bollinger(
        df, period=p["period"], stddev=p["stddev"], price_col=price_col
    )

    # CPR-like width (normalized) — guard divide-by-zero via abs(mid)+eps
    out = out.with_columns(
        (
            (pl.col("bb_upper") - pl.col("bb_lower"))
            / (pl.col("bb_mid").abs() + pl.lit(1e-9))
        ).alias("cpr_width")
    )

    # Upstream VPR support; default neutral 1.0
    if "VPR" not in out.columns:
        out = out.with_columns(pl.lit(1.0).alias("VPR"))

    # SPS: tighter width & stronger VPR → higher score
    out = out.with_columns(
        (pl.col("VPR") / (pl.lit(1.0) + pl.col("cpr_width"))).alias("SPS")
    )

    # Momentum context (pure Polars)
    out = out.with_columns(
        [
            pl.col(price_col).diff().alias("momentum"),
            pl.col(price_col)
            .diff()
            .rolling_mean(window_size=5)
            .alias("momentum_smooth"),
        ]
    ).with_columns((pl.col("momentum_smooth") > 0).cast(pl.Int8).alias("trend_up"))

    return out.fill_nan(None).fill_null(strategy="forward")


# ---------- registry export ----------
EXPORTS = {"pre_breakout": compute_pre_breakout}

if __name__ == "__main__":
    n = 200
    df = pl.DataFrame(
        {
            "close": pl.Series([100 + i * 0.05 for i in range(n)]),
            "high": pl.Series([100 + i * 0.06 for i in range(n)]),
            "low": pl.Series([100 + i * 0.04 for i in range(n)]),
            "volume": pl.Series([1_000 + (i % 10) * 50 for i in range(n)]),
        }
    )
    out = compute_pre_breakout(df, timeframe="15m")
    print(
        "✅ pre_breakout tail:\n", out.select(["cpr_width", "SPS", "trend_up"]).tail(5)
    )
