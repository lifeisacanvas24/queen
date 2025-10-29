# ============================================================
# queen/technicals/indicators/volume_mfi.py — v1.0 (forward-only)
# Money Flow Index (MFI) — settings-driven, NaN-safe, Polars/NumPy
# Outputs: ['mfi','mfi_norm','mfi_bias','mfi_flow']
# ============================================================
from __future__ import annotations

import numpy as np
import polars as pl
from queen.helpers.pl_compat import _s2np
from queen.settings.indicator_policy import params_for as _params_for


def mfi(
    df: pl.DataFrame,
    timeframe: str = "15m",
    *,
    period: int | None = None,
    overbought: float | None = None,
    oversold: float | None = None,
) -> pl.DataFrame:
    if not isinstance(df, pl.DataFrame):
        raise TypeError("mfi: expected a Polars DataFrame")
    need = {"high", "low", "close", "volume"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"mfi: missing required columns: {sorted(missing)}")

    p = _params_for("MFI", timeframe) or {}
    n = int(period or p.get("period", 14))
    ob = float(overbought or p.get("overbought", 70.0))
    os = float(oversold or p.get("oversold", 30.0))

    high = _s2np(df["high"])
    low = _s2np(df["low"])
    close = _s2np(df["close"])
    vol = _s2np(df["volume"])

    if len(close) < n + 2:
        zeros = np.zeros(len(close), dtype=float)
        return pl.DataFrame(
            {
                "mfi": zeros,
                "mfi_norm": zeros,
                "mfi_bias": np.array(["neutral"] * len(close), dtype=object),
                "mfi_flow": np.array(["flat"] * len(close), dtype=object),
            }
        )

    tp = (high + low + close) / 3.0
    rmf = tp * vol

    pos = np.zeros_like(rmf)
    neg = np.zeros_like(rmf)
    up = tp[1:] > tp[:-1]
    down = tp[1:] < tp[:-1]
    pos[1:][up] = rmf[1:][up]
    neg[1:][down] = rmf[1:][down]

    kernel = np.ones(n, dtype=float)
    pos_sum = np.convolve(pos, kernel, mode="valid")
    neg_sum = np.convolve(neg, kernel, mode="valid")

    mfr = pos_sum / (neg_sum + 1e-12)
    mfi_vals = 100.0 - (100.0 / (1.0 + mfr))

    mfi_full = np.concatenate([np.full(n - 1, np.nan), mfi_vals])
    mfi_norm = np.clip(np.nan_to_num(mfi_full / 100.0), 0.0, 1.0)

    bias = np.full(len(mfi_full), "neutral", dtype=object)
    bias[mfi_full > ob] = "distribution"
    bias[mfi_full < os] = "accumulation"

    delta = np.diff(np.nan_to_num(mfi_full, nan=0.0), prepend=0.0)
    flow = np.full(len(delta), "flat", dtype=object)
    flow[delta > 0] = "inflow"
    flow[delta < 0] = "outflow"

    return pl.DataFrame(
        {"mfi": mfi_full, "mfi_norm": mfi_norm, "mfi_bias": bias, "mfi_flow": flow}
    )


def summarize_mfi(df: pl.DataFrame) -> dict:
    if df.is_empty() or "mfi" not in df.columns:
        return {"status": "empty"}
    m = df["mfi"].drop_nans().drop_nulls()
    if m.is_empty():
        return {"status": "empty"}
    last = float(m[-1])
    bias = (
        str(df["mfi_bias"].drop_nulls()[-1]) if "mfi_bias" in df.columns else "neutral"
    )
    flow = str(df["mfi_flow"].drop_nulls()[-1]) if "mfi_flow" in df.columns else "flat"
    state = (
        "🟩 Accumulation"
        if bias == "accumulation"
        else "🟥 Distribution"
        if bias == "distribution"
        else "⬜ Neutral"
    )
    return {"MFI": round(last, 2), "Bias": bias, "Flow": flow, "State": state}


def attach_mfi(df: pl.DataFrame, timeframe: str = "15m") -> pl.DataFrame:
    return df.hstack(mfi(df, timeframe=timeframe))
