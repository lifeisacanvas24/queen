# ============================================================
# queen/technicals/indicators/all.py (v1.4 — Unified Orchestrator)
# ============================================================
from __future__ import annotations

import numpy as _np
import polars as pl


# ---------------- Helpers ----------------
def _safe_merge(df_base: pl.DataFrame, df_add: pl.DataFrame) -> pl.DataFrame:
    """Safely merge two DataFrames on shared keys (prefers timestamp/symbol)."""
    if df_base.is_empty():
        return df_add
    if df_add.is_empty():
        return df_base

    preferred = ["timestamp", "symbol"]
    shared = [c for c in preferred if c in df_base.columns and c in df_add.columns]
    if not shared:
        shared = [c for c in df_base.columns if c in df_add.columns]

    if shared:
        drop_cols = [
            c for c in df_add.columns if c in df_base.columns and c not in shared
        ]
        df_add = df_add.drop(drop_cols)
        return df_base.join(df_add, on=shared, how="inner")

    # no common keys → align by row
    return pl.concat([df_base, df_add], how="horizontal")


def _tf_from_context(context: str) -> str:
    """Map settings context → short timeframe tokens used by some engines."""
    ctx = (context or "").lower()
    if ctx.startswith("intraday_"):
        return ctx.split("_", 1)[1]  # e.g., 'intraday_15m' -> '15m'
    return {
        "hourly_1h": "1h",
        "daily": "1d",
        "weekly": "1w",
        "monthly": "1mo",
    }.get(ctx, "15m")


# ---------------- Main entrypoint ----------------
def attach_all_indicators(
    df: pl.DataFrame, context: str = "intraday_15m"
) -> pl.DataFrame:
    """Attach core + advanced engines safely, no side-effects."""
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    out = df

    # 1) Core primitives (EMA/RSI/MACD basic, ATR, VWAP)
    from .core import (
        attach_indicators as _attach_core,  # local import avoids graph issues
    )

    out = _attach_core(out)

    # 2) Keltner (KC_* + KC_norm) —— required for Vol Fusion later
    def _kc_inline_min(df_: pl.DataFrame) -> pl.DataFrame:
        """Minimal KC fallback: EMA(close, 20) ± 2 * ATR(14)."""
        if not {"high", "low", "close"}.issubset(df_.columns) or df_.height < 16:
            return pl.DataFrame()
        # --- ATR(14)
        prev_close = df_["close"].shift(1)
        tr1 = (df_["high"] - df_["low"]).abs()
        tr2 = (df_["high"] - prev_close).abs()
        tr3 = (df_["low"] - prev_close).abs()
        tr = pl.select(pl.max_horizontal(tr1, tr2, tr3).alias("tr")).to_series()
        atr14 = tr.ewm_mean(span=14, adjust=False).alias("KC_atr14")
        # --- EMA(close, 20)
        mid = df_["close"].ewm_mean(span=20, adjust=False).alias("KC_mid")
        # --- Bands (+ simple extras so callers can rely on names)
        upper = (pl.col("KC_mid") + 2.0 * pl.col("KC_atr14")).alias("KC_upper")
        lower = (pl.col("KC_mid") - 2.0 * pl.col("KC_atr14")).alias("KC_lower")
        kcdf = df_.with_columns([atr14, mid]).with_columns([upper, lower])
        # Width + normalized width (0..1, safe)
        width = (kcdf["KC_upper"] - kcdf["KC_lower"]).alias("KC_width")
        width_pct = ((width / (kcdf["KC_mid"].abs() + 1e-9)) * 100.0).alias(
            "KC_width_pct"
        )
        kcdf = kcdf.with_columns([width, width_pct])
        # Normalization
        wp = kcdf["KC_width_pct"].to_numpy()
        wmax = float(_np.nanmax(wp)) if wp.size else 0.0
        norm = (_np.clip(wp / (wmax if wmax > 0 else 1.0), 0.0, 1.0)).astype(float)
        return kcdf.with_columns(pl.Series("KC_norm", norm)).select(
            ["KC_mid", "KC_upper", "KC_lower", "KC_width", "KC_width_pct", "KC_norm"]
        )

    _kc_func = None
    try:
        from .keltner import compute_keltner as _kc_func  # canonical
    except Exception:
        try:
            from .vol_keltner import compute_keltner as _kc_func  # legacy filename
        except Exception:
            _kc_func = None

    kc_df = pl.DataFrame()
    if _kc_func is not None:
        try:
            kc_df = _kc_func(df=out, context=context)
            needed = {"KC_mid", "KC_upper", "KC_lower"}
            if not needed.issubset(set(kc_df.columns)):
                kc_df = pl.DataFrame()
        except Exception:
            kc_df = pl.DataFrame()

    if kc_df.is_empty():
        kc_df = _kc_inline_min(out)

    if not kc_df.is_empty():
        out = _safe_merge(out, kc_df)

    # 3) Momentum MACD (normalized, slope, crossover)
    def _macd_inline_min(df_: pl.DataFrame) -> pl.DataFrame:
        """Minimal MACD fallback with the expected column names."""
        if "close" not in df_.columns or df_.height < 26:
            # keep shapes aligned with empty DF to avoid merge errors
            return pl.DataFrame()
        close = df_["close"].cast(pl.Float64)
        ema_fast = close.ewm_mean(span=12, adjust=False)
        ema_slow = close.ewm_mean(span=26, adjust=False)
        macd_line = (ema_fast - ema_slow).alias("MACD_line")
        signal = macd_line.ewm_mean(span=9, adjust=False).alias("MACD_signal")
        hist = (pl.col("MACD_line") - pl.col("MACD_signal")).alias("MACD_hist")
        tmp = df_.with_columns([macd_line, signal]).with_columns([hist])
        # norm & slope & crossover
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

    mm_df = pl.DataFrame()
    try:
        from .momentum_macd import compute_macd as _mm

        mm_df = _mm(df=out, context=context)
        needed = {"MACD_line", "MACD_signal", "MACD_hist"}
        if not needed.issubset(set(mm_df.columns)):
            mm_df = pl.DataFrame()
    except Exception:
        mm_df = pl.DataFrame()

    if mm_df.is_empty():
        mm_df = _macd_inline_min(out)

    if not mm_df.is_empty():
        out = _safe_merge(out, mm_df)

    # 4) Chaikin (volume flow)
    try:
        from .volume_chaikin import chaikin as _chaikin

        tf = _tf_from_context(context)
        ch = _chaikin(df=out, timeframe=tf)
        out = _safe_merge(out, ch)
    except Exception:
        pass

    # 5) MFI (volume momentum)
    try:
        from .volume_mfi import mfi as _mfi

        mfi_df = _mfi(df=out, timeframe=_tf_from_context(context))
        out = _safe_merge(out, mfi_df)
    except Exception:
        pass

    # 6) Breadth engines (cumulative + momentum)
    try:
        from .breadth_cumulative import compute_breadth as _bc

        b1 = _bc(df=out, context=context)
        out = _safe_merge(out, b1)
    except Exception:
        pass

    try:
        from .breadth_momentum import compute_breadth_momentum as _bm

        b2 = _bm(df=out, context=context)
        out = _safe_merge(out, b2)
    except Exception:
        pass

    if "timestamp" in out.columns:
        out = out.sort("timestamp")
    return out
