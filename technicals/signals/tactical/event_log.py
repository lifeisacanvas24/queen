# ============================================================
# queen/technicals/signals/tactical/event_log.py
# ------------------------------------------------------------
# 🧭 Unified Tactical Event Logger (Phase 4.9 • settings-driven)
# Collects tactical outputs and appends structured analytics
# records into SETTINGS.PATHS["LOGS"]/tactical_event_log.csv
# ============================================================
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import polars as pl

try:
    from queen.settings import settings as SETTINGS  # canonical paths
except Exception:
    SETTINGS = None


# ------------------------------------------------------------
# 🧩 Safe value getter (last row, tolerant to missing/nulls)
# ------------------------------------------------------------
def _last(df: pl.DataFrame, col: str):
    if col not in df.columns or df.is_empty():
        return None
    s = df.get_column(col)
    # prefer last non-null if present
    nz = s.drop_nulls()
    return (nz[-1] if nz.len() else s[-1]) if s.len() else None


# ------------------------------------------------------------
# ⚙️ Main function — Event Log Writer (Polars I/O, de-duped)
# ------------------------------------------------------------
def log_tactical_events(global_health_dfs: Dict[str, pl.DataFrame]) -> pl.DataFrame:
    """
    Parameters
    ----------
    global_health_dfs : dict[str, pl.DataFrame]
        Mapping { timeframe: df } containing latest tactical data per TF.

    Returns
    -------
    pl.DataFrame
        The freshly created records (one per timeframe).
    """
    # Resolve paths via settings (DRY)
    if SETTINGS:
        log_dir = SETTINGS.PATHS["LOGS"]
    else:
        from pathlib import Path as _P

        log_dir = _P("queen/data/runtime/logs")

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tactical_event_log.csv"

    now_utc = datetime.now(timezone.utc).isoformat()
    records = []

    # Collect the last state from each timeframe (strictly optional columns)
    for tf, df in global_health_dfs.items():
        records.append(
            {
                "timestamp": now_utc,
                "timeframe": tf,
                "CMV": _last(df, "CMV"),
                "CMV_Bias": _last(df, "CMV_Bias"),
                "Bias_Regime": _last(df, "Regime_Emoji"),
                "Divergence": _last(df, "Divergence_Signal"),
                "Liquidity_Trap": _last(df, "Liquidity_Trap"),
                "Absorption": _last(df, "Absorption_Zone"),
                "Squeeze": _last(df, "Squeeze_Signal"),
                "Exhaustion": _last(df, "Exhaustion_Signal"),
                "Reversal_Alert": _last(df, "Reversal_Alert"),
                "Reversal_Score": _last(df, "Reversal_Score"),
                "Confidence": _last(df, "Reversal_Confidence"),
                "CMV_Flip": _last(df, "CMV_Flip"),
                "SPS": _last(df, "SPS"),
                "Volume": _last(df, "volume"),
            }
        )

    df_new = pl.DataFrame(records)

    # Append safely with de-dup by (timestamp, timeframe)
    if log_file.exists():
        df_existing = pl.read_csv(log_file)
        df_all = pl.concat([df_existing, df_new], how="vertical_relaxed")
        df_all = df_all.unique(subset=["timestamp", "timeframe"], keep="last")
    else:
        df_all = df_new

    df_all.write_csv(log_file)
    return df_new


# ------------------------------------------------------------
# 🧪 Stand-alone smoke (optional)
# ------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    dummy = {
        "5m": pl.DataFrame(
            {
                "CMV": np.random.randn(5),
                "CMV_Bias": ["🟢"] * 5,
                "Regime_Emoji": ["🟢 Trend"] * 5,
                "Divergence_Signal": ["➡️ Stable"] * 5,
                "Absorption_Zone": ["➡️ Stable"] * 5,
                "Exhaustion_Signal": ["➡️ Stable"] * 5,
                "Reversal_Alert": ["➡️ Stable"] * 5,
                "Reversal_Score": [1.2] * 5,
                "Reversal_Confidence": ["LOW"] * 5,
                "CMV_Flip": [False] * 5,
                "SPS": [0.3] * 5,
                "volume": [3500] * 5,
            }
        ),
        "15m": pl.DataFrame(
            {
                "CMV": np.random.randn(3),
                "CMV_Bias": ["🔻"] * 3,
                "Regime_Emoji": ["⚫ Neutral"] * 3,
                "Divergence_Signal": ["➡️ Stable"] * 3,
                "Absorption_Zone": ["➡️ Stable"] * 3,
                "Exhaustion_Signal": ["➡️ Stable"] * 3,
                "Reversal_Alert": ["➡️ Stable"] * 3,
                "Reversal_Score": [2.1] * 3,
                "Reversal_Confidence": ["MED"] * 3,
                "CMV_Flip": [True, False, True],
                "SPS": [0.6] * 3,
                "volume": [4200] * 3,
            }
        ),
    }

    out = log_tactical_events(dummy)
    print("Logged rows:\n", out)
