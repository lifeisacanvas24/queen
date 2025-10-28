# ============================================================
# queen/technicals/signals/tactical/helpers.py — Tactical Input Auto-Builder v1.0
# ============================================================
"""Auto-computes tactical fusion inputs (RScore, VolX, LBX)
from available indicator modules, with graceful fallbacks.
"""

from __future__ import annotations

import polars as pl
from quant.utils.logs import get_logger

logger = get_logger("TacticalHelper")


def compute_tactical_inputs(df: pl.DataFrame) -> dict:
    """Return tactical inputs RScore, VolX, LBX from indicators."""
    results = {"RScore": 0.0, "VolX": 0.0, "LBX": 0.0}

    try:
        from quant.indicators import breadth_momentum, trend_adx_dmi, vol_keltner

        # --- RScore: Breadth Momentum / Strength
        if hasattr(breadth_momentum, "compute_rscore"):
            results["RScore"] = float(breadth_momentum.compute_rscore(df))
        elif hasattr(breadth_momentum, "compute_breadth_momentum"):
            r = breadth_momentum.compute_breadth_momentum(df)
            results["RScore"] = (
                float(r.get("breadth_strength", 0))
                if isinstance(r, dict)
                else float(r or 0)
            )

        # --- VolX: Volatility Index (from Keltner / ATR)
        if hasattr(vol_keltner, "compute_volatility_index"):
            results["VolX"] = float(vol_keltner.compute_volatility_index(df))
        elif hasattr(vol_keltner, "compute_keltner"):
            v = vol_keltner.compute_keltner(df)
            results["VolX"] = (
                float(v.get("vol_index", 0)) if isinstance(v, dict) else float(v or 0)
            )

        # --- LBX: Trend / ADX Strength
        if hasattr(trend_adx_dmi, "compute_lbx"):
            results["LBX"] = float(trend_adx_dmi.compute_lbx(df))
        elif hasattr(trend_adx_dmi, "compute_adx_dmi"):
            t = trend_adx_dmi.compute_adx_dmi(df)
            results["LBX"] = (
                float(t.get("trend_strength", 0))
                if isinstance(t, dict)
                else float(t or 0)
            )

        logger.info(f"[TacticalHelper] ✅ Computed tactical inputs: {results}")
        return results

    except Exception as e:
        logger.warning(
            f"[TacticalHelper] ⚠️ Fallback used — unable to compute all tactical inputs: {e}"
        )
        return results
