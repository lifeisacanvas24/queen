# ============================================================
# queen/technicals/signals/templates/indicator_template.py
# ------------------------------------------------------------
# 🧱 Headless Indicator Template — v2 (settings-driven, 100% Polars)
# - Pulls defaults/contexts from queen.settings.indicators
# - Uses common.timeframe_key + indicator_kwargs
# - Pure Polars (no numpy math needed for baseline)
# - Exports into registry via EXPORTS
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import polars as pl
from queen.helpers.common import indicator_kwargs, timeframe_key
from queen.helpers.logger import log
from queen.settings import indicators as IND  # data-only registry
from queen.settings import settings as SETTINGS

IND_NAME = "TEMPLATE_INDICATOR"  # <— rename when copying


# ---------- params resolver (settings-owned) ----------
def _params_for(tf_token: str | None) -> Dict[str, Any]:
    block = IND.get_block(IND_NAME) or {}
    base = dict(block.get("default", {}))
    if tf_token:
        ctx_key = timeframe_key(tf_token)
        override = (block.get("contexts", {}) or {}).get(ctx_key, {})
        base.update(override or {})
    return indicator_kwargs(base)


# ---------- core compute ----------
def compute_indicator(
    df: pl.DataFrame,
    *,
    timeframe: str | None = None,
    column: str = "close",
) -> pl.DataFrame:
    """Minimal headless pattern:
    • validates required columns
    • reads params from settings.indicators
    • appends result columns
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    if column not in df.columns:
        log.warning(f"[{IND_NAME}] missing '{column}' — skipped.")
        return df

    p = _params_for(timeframe)
    lookback = int(p.get("lookback", 14))

    # rolling mean (same-length output) + normalized [0,1]
    rm = pl.col(column).rolling_mean(lookback).alias("template_value")
    # min/max over window to avoid global squeeze; fall back to global if needed
    minw = pl.col(column).rolling_min(lookback)
    maxw = pl.col(column).rolling_max(lookback)
    norm = ((rm - minw) / (pl.max_horizontal(pl.lit(1e-12), (maxw - minw)))).alias(
        "template_norm"
    )

    return df.with_columns([rm, norm])


# ---------- summarizer ----------
def summarize_indicator(df: pl.DataFrame) -> Dict[str, Any]:
    if df.is_empty() or "template_value" not in df.columns:
        return {"status": "empty"}
    last = df.select(pl.col("template_value").tail(1)).item()
    bias = "bullish" if float(last) > 0 else "bearish"
    return {"value": float(last), "bias": bias}


# ---------- registry export ----------
EXPORTS = {"template_indicator": compute_indicator}

if __name__ == "__main__":
    n = 200
    df = pl.DataFrame({"close": pl.Series([100 + i * 0.05 for i in range(n)])})
    out = compute_indicator(df, timeframe="15m")
    print("✅ template summary:", summarize_indicator(out))
