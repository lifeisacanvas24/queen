#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/all.py — v2.1 (Settings-Driven Orchestrator)
# ------------------------------------------------------------
# • Central place to attach ALL key indicators used by the engine
# • Respects settings/indicator_policy per timeframe
# • Separates context key ("intraday_15m") from timeframe token ("15m")
# • Safe fallbacks (inline Keltner / MACD) to avoid hard failures
# • Now also wires in advanced overlays + state features via advanced.attach_advanced
# ============================================================

from __future__ import annotations

from typing import Sequence

import numpy as _np
import polars as pl

from queen.helpers.logger import log
from queen.settings.indicator_policy import params_for as _params_for

from .core import (
    ema as _ema,
    ema_slope as _ema_slope,
    rsi as _rsi,
    vwap as _vwap,
    atr as _atr,
)
from .advanced import attach_advanced as _attach_advanced


# ------------------------------------------------------------
# 🧩 Helpers
# ------------------------------------------------------------
def _safe_merge(df_base: pl.DataFrame, df_add: pl.DataFrame) -> pl.DataFrame:
    """Safely merge two DataFrames on shared keys (prefers timestamp/symbol)."""
    if df_base.is_empty():
        return df_add
    if df_add.is_empty():
        return df_base

    preferred: Sequence[str] = ("timestamp", "symbol")
    shared = [c for c in preferred if c in df_base.columns and c in df_add.columns]
    if not shared:
        shared = [c for c in df_base.columns if c in df_add.columns]

    if shared:
        drop_cols = [c for c in df_add.columns if c in df_base.columns and c not in shared]
        if drop_cols:
            df_add = df_add.drop(drop_cols)
        return df_base.join(df_add, on=shared, how="inner")

    # No common keys → align by row index
    return pl.concat([df_base, df_add], how="horizontal")


def _tf_from_context(context: str) -> str:
    """Map settings context key → short timeframe token used by indicator_policy."""
    ctx = (context or "").strip().lower()
    if ctx.startswith("intraday_"):
        # e.g., 'intraday_15m' -> '15m'
        return ctx.split("_", 1)[1]

    return {
        "hourly_1h": "1h",
        "hourly_2h": "2h",
        "hourly_4h": "4h",
        "daily": "1d",
        "weekly": "1w",
        "monthly": "1mo",
    }.get(ctx, "15m")


# ------------------------------------------------------------
# 1) Core indicators (EMA / RSI / ATR / VWAP)
# ------------------------------------------------------------
def _attach_core_indicators(df: pl.DataFrame, tf_token: str) -> pl.DataFrame:
    """Attach core EMA/RSI/ATR/VWAP using settings/indicator_policy."""
    if df.is_empty():
        return df

    out = df

    # Resolve parameters from settings/indicator_policy
    p_ema = _params_for("EMA", tf_token) or {}
    p_ema_cross = _params_for("EMA_CROSS", tf_token) or {}
    p_rsi = _params_for("RSI", tf_token) or {}
    p_atr = _params_for("ATR", tf_token) or {}

    base_len = int(p_ema.get("length", 21))
    fast_len = int(p_ema_cross.get("fast", 20))
    slow_len = int(p_ema_cross.get("slow", 50))
    rsi_period = int(p_rsi.get("period", 14))
    atr_period = int(p_atr.get("period", 14))

    cols: list[pl.Series] = []

    # --- EMA(s) with NO duplicates ---
    ema_periods: list[int] = []
    for p in (base_len, fast_len, slow_len):
        if p not in ema_periods:
            ema_periods.append(p)

    for p in ema_periods:
        try:
            cols.append(_ema(out, period=p).alias(f"ema_{p}"))
        except Exception as e:
            log.warning(f"[IND] EMA(period={p}) failed for tf={tf_token}: {e}")

    # EMA slope for the fast leg (name is unique: ema_<fast>_slope1)
    try:
        cols.append(_ema_slope(out, length=fast_len, periods=1))
    except Exception as e:
        log.warning(
            f"[IND] EMA_SLOPE(fast={fast_len}) failed tf={tf_token}: {e}"
        )

    # RSI
    try:
        cols.append(_rsi(out, period=rsi_period))
    except Exception as e:
        log.warning(f"[IND] RSI(period={rsi_period}) failed tf={tf_token}: {e}")

    # ATR
    try:
        cols.append(_atr(out, period=atr_period))
    except Exception as e:
        log.warning(f"[IND] ATR(period={atr_period}) failed tf={tf_token}: {e}")

    # VWAP
    try:
        cols.append(_vwap(out))
    except Exception as e:
        log.warning(f"[IND] VWAP failed: {e}")

    if cols:
        out = out.with_columns(cols)
    return out

# ------------------------------------------------------------
# 2) Keltner Channel (Volatility backbone for VolFusion / SPS)
# ------------------------------------------------------------
def _kc_inline_min(df_: pl.DataFrame) -> pl.DataFrame:
    """Minimal Keltner fallback: EMA(close,20) ± 2 * ATR(14) + normalized width."""
    if not {"high", "low", "close"}.issubset(df_.columns) or df_.height < 16:
        return pl.DataFrame()

    # True Range → ATR(14)
    prev_close = df_["close"].shift(1)
    tr1 = (df_["high"] - df_["low"]).abs()
    tr2 = (df_["high"] - prev_close).abs()
    tr3 = (df_["low"] - prev_close).abs()

    tr = pl.select(pl.max_horizontal(tr1, tr2, tr3).alias("tr")).to_series()
    atr14 = tr.ewm_mean(span=14, adjust=False).alias("KC_atr14")

    # EMA(close, 20) midline
    mid = df_["close"].ewm_mean(span=20, adjust=False).alias("KC_mid")

    kcdf = df_.with_columns([atr14, mid])
    upper = (kcdf["KC_mid"] + 2.0 * kcdf["KC_atr14"]).alias("KC_upper")
    lower = (kcdf["KC_mid"] - 2.0 * kcdf["KC_atr14"]).alias("KC_lower")
    kcdf = kcdf.with_columns([upper, lower])

    width = (kcdf["KC_upper"] - kcdf["KC_lower"]).alias("KC_width")
    width_pct = ((width / (kcdf["KC_mid"].abs() + 1e-9)) * 100.0).alias("KC_width_pct")
    kcdf = kcdf.with_columns([width, width_pct])

    wp = kcdf["KC_width_pct"].to_numpy()
    wmax = float(_np.nanmax(wp)) if wp.size else 0.0
    if not _np.isfinite(wmax) or wmax <= 0:
        wmax = 1.0
    norm = _np.clip(wp / wmax, 0.0, 1.0)

    return kcdf.with_columns(pl.Series("KC_norm", norm)).select(
        ["KC_mid", "KC_upper", "KC_lower", "KC_width", "KC_width_pct", "KC_norm"]
    )


def _attach_keltner(df: pl.DataFrame, context: str, tf_token: str) -> pl.DataFrame:
    """Attach Keltner bands, using canonical implementation if available."""
    out = df
    kc_df = pl.DataFrame()

    # Preferred: canonical implementation (if present)
    kc_func = None
    try:
        from .keltner import compute_keltner as kc_func  # type: ignore[attr-defined]
    except Exception:
        try:
            from .vol_keltner import compute_keltner as kc_func  # legacy filename
        except Exception:
            kc_func = None

    if kc_func is not None:
        try:
            kc_df = kc_func(df=out, context=context, timeframe=tf_token)
            needed = {"KC_mid", "KC_upper", "KC_lower"}
            if not needed.issubset(set(kc_df.columns)):
                log.warning(
                    "[IND] Keltner canonical missing expected columns, fallback → inline"
                )
                kc_df = pl.DataFrame()
        except Exception as e:
            log.warning(f"[IND] Keltner canonical failed → {e}")
            kc_df = pl.DataFrame()

    if kc_df.is_empty():
        kc_df = _kc_inline_min(out)

    if kc_df.is_empty():
        return out

    return _safe_merge(out, kc_df)


# ------------------------------------------------------------
# 3) MACD (config-driven, with normalized hist/slope/crossover)
# ------------------------------------------------------------
def _macd_inline_min(df_: pl.DataFrame) -> pl.DataFrame:
    """Minimal MACD fallback with normalized histogram/slope & crossover."""
    if "close" not in df_.columns or df_.height < 26:
        return pl.DataFrame()

    close = df_["close"].cast(pl.Float64)
    ema_fast = close.ewm_mean(span=12, adjust=False)
    ema_slow = close.ewm_mean(span=26, adjust=False)
    macd_line = (ema_fast - ema_slow).alias("MACD_line")
    signal = macd_line.ewm_mean(span=9, adjust=False).alias("MACD_signal")
    hist_expr = (pl.col("MACD_line") - pl.col("MACD_signal")).alias("MACD_hist")

    tmp = df_.with_columns([macd_line, signal]).with_columns([hist_expr])

    h_np = tmp["MACD_hist"].to_numpy()
    h_max = float(_np.nanmax(_np.abs(h_np))) if h_np.size else 1.0
    if not _np.isfinite(h_max) or h_max == 0:
        h_max = 1.0
    norm = _np.clip(h_np / h_max, -1.0, 1.0)

    line_np = tmp["MACD_line"].to_numpy()
    slope = _np.gradient(line_np)
    s_max = float(_np.nanmax(_np.abs(slope))) if slope.size else 1.0
    if not _np.isfinite(s_max) or s_max == 0:
        s_max = 1.0
    slope_norm = _np.clip(slope / s_max, -1.0, 1.0)

    crossover = (tmp["MACD_line"] > tmp["MACD_signal"]).to_numpy()

    return tmp.with_columns(
        [
            pl.Series("MACD_norm", norm),
            pl.Series("MACD_slope", slope_norm),
            pl.Series("MACD_crossover", crossover),
        ]
    ).select(
        [
            "MACD_line",
            "MACD_signal",
            "MACD_hist",
            "MACD_norm",
            "MACD_slope",
            "MACD_crossover",
        ]
    )


def _attach_macd(df: pl.DataFrame, tf_token: str) -> pl.DataFrame:
    """Attach MACD block via momentum_macd (settings-driven) with fallback."""
    out = df
    mm_df = pl.DataFrame()

    try:
        from .momentum_macd import compute_macd as _mm  # type: ignore[attr-defined]

        mm_df = _mm(df=out, timeframe=tf_token)
        needed = {"MACD_line", "MACD_signal", "MACD_hist"}
        if not needed.issubset(set(mm_df.columns)):
            log.warning(
                "[IND] momentum_macd missing expected columns, fallback → inline"
            )
            mm_df = pl.DataFrame()
    except Exception as e:
        log.warning(f"[IND] momentum_macd import/exec failed → {e}")
        mm_df = pl.DataFrame()

    if mm_df.is_empty():
        mm_df = _macd_inline_min(out)

    if mm_df.is_empty():
        return out

    return _safe_merge(out, mm_df)


# ------------------------------------------------------------
# 4) Volume Flow: Chaikin / MFI
# ------------------------------------------------------------
def _attach_volume_flows(
    df: pl.DataFrame, context: str, tf_token: str
) -> pl.DataFrame:
    out = df

    # Chaikin (ADL-based flow)
    try:
        from .volume_chaikin import chaikin as _chaikin  # type: ignore[attr-defined]

        ch = _chaikin(df=out, timeframe=tf_token)
        out = _safe_merge(out, ch)
    except Exception as e:
        log.warning(f"[IND] Chaikin volume flow failed → {e}")

    # MFI (volume-weighted RSI)
    try:
        from .volume_mfi import mfi as _mfi  # type: ignore[attr-defined]

        mfi_df = _mfi(df=out, timeframe=tf_token)
        out = _safe_merge(out, mfi_df)
    except Exception as e:
        log.warning(f"[IND] MFI failed → {e}")

    return out


# ------------------------------------------------------------
# 5) Breadth Engines
# ------------------------------------------------------------
def _attach_breadth(df: pl.DataFrame, context: str) -> pl.DataFrame:
    out = df

    # Cumulative breadth
    try:
        from .breadth_cumulative import compute_breadth as _bc  # type: ignore[attr-defined]

        b1 = _bc(df=out, context=context)
        out = _safe_merge(out, b1)
    except Exception as e:
        log.warning(f"[IND] Breadth CUM failed → {e}")

    # Momentum breadth
    try:
        from .breadth_momentum import compute_breadth_momentum as _bm  # type: ignore[attr-defined]

        b2 = _bm(df=out, context=context)
        out = _safe_merge(out, b2)
    except Exception as e:
        log.warning(f"[IND] Breadth MOM failed → {e}")

    return out


# ------------------------------------------------------------
# 🌐 Public Entrypoint
# ------------------------------------------------------------
def attach_all_indicators(
    df: pl.DataFrame, context: str = "intraday_15m"
) -> pl.DataFrame:
    """Attach all core + advanced indicators used by the engine.

    Args:
        df: OHLCV DataFrame, ideally with 'timestamp' and 'symbol' columns.
        context: settings context key, e.g. 'intraday_15m', 'daily', 'weekly'.

    Returns:
        DataFrame with indicator columns attached. Safe against partial failures.
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    tf_token = _tf_from_context(context)
    out = df.clone()

    # 1) Core indicators
    out = _attach_core_indicators(out, tf_token=tf_token)

    # 2) Keltner backbone
    out = _attach_keltner(out, context=context, tf_token=tf_token)

    # 3) MACD (config-driven)
    out = _attach_macd(out, tf_token=tf_token)

    # 4) Volume flows (Chaikin/MFI)
    out = _attach_volume_flows(out, context=context, tf_token=tf_token)

    # 5) Breadth engines
    out = _attach_breadth(out, context=context)

    # 6) Advanced overlays + Bible v10.5 state features
    try:
        out = _attach_advanced(out, context=context)
    except Exception as e:
        log.warning(f"[IND] attach_advanced failed for context={context}: {e}")

    if "timestamp" in out.columns:
        out = out.sort("timestamp")

    return out


__all__ = ["attach_all_indicators"]
