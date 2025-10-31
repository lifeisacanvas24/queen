# ============================================================
# queen/technicals/indicators/volume_mfi.py — v1.1 (forward-only)
# Money Flow Index (MFI) — settings-driven, NaN-safe, Polars/NumPy
# Outputs: ['MFI','MFI_norm','MFI_Bias','MFI_Flow']
# ============================================================
from __future__ import annotations

import numpy as np
import polars as pl
from queen.helpers.pl_compat import _s2np
from queen.settings.indicator_policy import params_for as _params_for


def _tf_from_context(context: str) -> str:
    c = (context or "").lower()
    if c.startswith("intraday_"):
        return c.split("_", 1)[-1]  # '15m'
    if c.startswith("hourly_"):
        return c.split("_", 1)[-1]  # '1h'
    if c in {"daily", "1d", "d"}:
        return "1d"
    if c in {"weekly", "1w", "w"}:
        return "1w"
    return c or "15m"


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
                "MFI": zeros,
                "MFI_norm": zeros,
                "MFI_Bias": np.array(["⬜ Neutral"] * len(close), dtype=object),
                "MFI_Flow": np.array(["➡️ Flat"] * len(close), dtype=object),
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

    bias = np.full(len(mfi_full), "⬜ Neutral", dtype=object)
    bias[mfi_full > ob] = "🟥 Distribution"
    bias[mfi_full < os] = "🟩 Accumulation"

    delta = np.diff(np.nan_to_num(mfi_full, nan=0.0), prepend=0.0)
    flow = np.full(len(delta), "➡️ Flat", dtype=object)
    flow[delta > 0] = "⬆️ Inflow"
    flow[delta < 0] = "⬇️ Outflow"

    return pl.DataFrame(
        {"MFI": mfi_full, "MFI_norm": mfi_norm, "MFI_Bias": bias, "MFI_Flow": flow}
    )


def compute_mfi(df: pl.DataFrame, context: str = "intraday_15m") -> pl.DataFrame:
    """Compatibility wrapper for orchestrators/tests that pass 'context'."""
    tf = _tf_from_context(context)
    return mfi(df, timeframe=tf)


def summarize_mfi(df: pl.DataFrame) -> dict:
    if df.is_empty() or "MFI" not in df.columns:
        return {"status": "empty"}
    m = df["MFI"].drop_nans().drop_nulls()
    if m.is_empty():
        return {"status": "empty"}
    last = float(m[-1])
    bias = (
        str(df["MFI_Bias"].drop_nulls()[-1])
        if "MFI_Bias" in df.columns
        else "⬜ Neutral"
    )
    flow = (
        str(df["MFI_Flow"].drop_nulls()[-1]) if "MFI_Flow" in df.columns else "➡️ Flat"
    )
    state = (
        "🟩 Accumulation"
        if "Accumulation" in bias
        else ("🟥 Distribution" if "Distribution" in bias else "⬜ Neutral")
    )
    return {"MFI": round(last, 2), "Bias": bias, "Flow": flow, "State": state}


def attach_mfi(df: pl.DataFrame, timeframe: str = "15m") -> pl.DataFrame:
    return df.hstack(mfi(df, timeframe=timeframe))
