# ============================================================
# queen/technicals/signals/tactical/helpers.py — Tactical Input Auto-Builder (v2)
# ============================================================
from __future__ import annotations

import polars as pl

from queen.helpers.logger import log

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None

__all__ = ["compute_tactical_inputs"]
EXPORTS = {"tactical_inputs": lambda df, **kw: compute_tactical_inputs(df, **kw)}


def _norm01(expr: pl.Expr) -> pl.Expr:
    lo = expr.min()
    hi = expr.max()
    rng = hi - lo
    return pl.when(rng == 0).then(0.0).otherwise((expr - lo) / rng)


def _atr_fallback(df: pl.DataFrame, lookback: int = 14) -> pl.Expr:
    # True range as abs(high-low) only (API-agnostic, fast)
    tr = (pl.col("high") - pl.col("low")).abs()
    try:
        atr = tr.rolling_mean(window_size=lookback)
    except TypeError:
        atr = tr.rolling_mean(window=lookback)
    # VolX_norm ≈ normalized ATR
    return _norm01(atr).alias("VolX_norm")


def _lbx_fallback(df: pl.DataFrame) -> pl.Expr:
    # Use CMV(−1..1) & SPS(0..1) if present; else zeros
    cmv = pl.col("CMV").fill_null(0.0) if "CMV" in df.columns else pl.lit(0.0)
    sps = pl.col("SPS").fill_null(0.0) if "SPS" in df.columns else pl.lit(0.0)
    # crude breadth-like mix, then normalize 0..1
    raw = (cmv + sps) / 2.0
    return _norm01(raw).alias("LBX_norm")


def _rscore_blend(lbx_norm: pl.Expr, volx_norm: pl.Expr) -> pl.Expr:
    # Risk-on prefers low vol → invert volx
    r = 0.5 * lbx_norm + 0.5 * (1.0 - volx_norm)
    return _norm01(r).alias("RScore_norm")


def compute_tactical_inputs(
    df: pl.DataFrame,
    *,
    context: str = "intraday_15m",
) -> dict[str, float]:
    """
    Returns dict: {"RScore": float, "VolX": float, "LBX": float}
    Uses native fusion modules if present; otherwise robust fallbacks.
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {"RScore": 0.0, "VolX": 0.0, "LBX": 0.0}

    out = df

    # ---------------- 1) VolX_norm ----------------
    volx_norm_expr: pl.Expr | None = None
    try:
        from queen.technicals.signals.fusion.volatility_fusion import (
            compute_volatility_fusion,
        )  # optional

        vdf = compute_volatility_fusion(out, context=context)
        if "VolX_norm" in vdf.columns:
            volx_norm_expr = pl.lit(vdf["VolX_norm"]).alias("VolX_norm")
    except Exception as e:
        log.debug(f"[TacticalHelper] VolX fusion unavailable → {e}")

    if volx_norm_expr is None:
        volx_norm_expr = _atr_fallback(out)

    # ---------------- 2) LBX_norm -----------------
    lbx_norm_expr: pl.Expr | None = None
    try:
        from queen.technicals.signals.fusion.liquidity_breadth import (
            compute_liquidity_breadth_fusion,
        )  # preferred path

        ldf = compute_liquidity_breadth_fusion(out, context=context)
        if "LBX_norm" in ldf.columns:
            lbx_norm_expr = pl.lit(ldf["LBX_norm"]).alias("LBX_norm")
    except Exception as e:
        log.debug(f"[TacticalHelper] LBX fusion unavailable → {e}")

    if lbx_norm_expr is None:
        lbx_norm_expr = _lbx_fallback(out)

    # ---------------- 3) RScore_norm --------------
    rscore_norm_expr: pl.Expr | None = None
    try:
        from queen.technicals.signals.fusion.market_regime import compute_market_regime

        rdf = compute_market_regime(out, context=context)
        if "RScore_norm" in rdf.columns:
            rscore_norm_expr = pl.lit(rdf["RScore_norm"]).alias("RScore_norm")
    except Exception as e:
        log.debug(f"[TacticalHelper] RScore fusion unavailable → {e}")

    if rscore_norm_expr is None:
        rscore_norm_expr = _rscore_blend(
            lbx_norm_expr,
            volx_norm_expr,  # type: ignore[arg-type]
        )

    # ---------------- materialize + reduce --------
    tmp = out.select(
        [
            rscore_norm_expr,
            volx_norm_expr,  # type: ignore[arg-type]
            lbx_norm_expr,  # type: ignore[arg-type]
        ]
    ).with_columns(
        [
            (pl.col("RScore_norm").mean()).alias("_r_mean"),
            (pl.col("VolX_norm").mean()).alias("_v_mean"),
            (pl.col("LBX_norm").mean()).alias("_l_mean"),
        ]
    )

    r = float(tmp["_r_mean"][0])
    v = float(tmp["_v_mean"][0])
    l = float(tmp["_l_mean"][0])

    log.info(f"[TacticalHelper] ✅ inputs → RScore={r:.3f}, VolX={v:.3f}, LBX={l:.3f}")
    return {"RScore": r, "VolX": v, "LBX": l}
