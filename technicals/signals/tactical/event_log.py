# ============================================================
# queen/technicals/signals/tactical/event_log.py
# ------------------------------------------------------------
# 🧭 Unified Tactical Event Logger (Phase 4.9)
# Collects tactical engine outputs and appends structured
# analytics records into quant/logs/tactical_event_log.csv
# ============================================================

import datetime
import os

import polars as pl


# ------------------------------------------------------------
# 🧩 Utility — Safe Value Getter
# ------------------------------------------------------------
def safe_get(df: pl.DataFrame, col: str):
    """Return last value of column if it exists, else None."""
    if col in df.columns:
        return df[col][-1]
    return None


# ------------------------------------------------------------
# ⚙️ Main Function — Event Log Writer
# ------------------------------------------------------------
def log_tactical_events(global_health_dfs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Collects tactical outputs across all timeframes and appends them
    to quant/logs/tactical_event_log.csv

    Parameters
    ----------
    global_health_dfs : dict
        { timeframe: Polars DataFrame } mapping containing latest tactical data.

    Returns
    -------
    pl.DataFrame
        Summary of newly logged events.

    """
    log_dir = "quant/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "tactical_event_log.csv")

    records = []
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # --------------------------------------------------------
    # 🧠 Collect the last state from each timeframe
    # --------------------------------------------------------
    for tf, df in global_health_dfs.items():
        record = {
            "timestamp": now_utc,
            "timeframe": tf,
            "CMV": safe_get(df, "CMV"),
            "CMV_Bias": safe_get(df, "CMV_Bias"),
            "Bias_Regime": safe_get(df, "Regime_Emoji"),
            "Divergence": safe_get(df, "Divergence_Signal"),
            "Liquidity_Trap": safe_get(df, "Liquidity_Trap"),
            "Absorption": safe_get(df, "Absorption_Zone"),
            "Squeeze": safe_get(df, "Squeeze_Signal"),
            "Exhaustion": safe_get(df, "Exhaustion_Signal"),
            "Reversal_Alert": safe_get(df, "Reversal_Alert"),
            "Reversal_Score": safe_get(df, "Reversal_Score"),
            "Confidence": safe_get(df, "Reversal_Confidence"),
            "CMV_Flip": safe_get(df, "CMV_Flip"),
            "SPS": safe_get(df, "SPS"),
            "Volume": safe_get(df, "volume"),
        }
        records.append(record)

    df_new = pl.DataFrame(records)

    # --------------------------------------------------------
    # 💾 Append safely to CSV (deduplicate)
    # --------------------------------------------------------
    if os.path.exists(log_file):
        df_existing = pl.read_csv(log_file)
        df_all = pl.concat([df_existing, df_new], how="vertical_relaxed")
        df_all = df_all.unique(subset=["timestamp", "timeframe"])
    else:
        df_all = df_new

    df_all.write_csv(log_file)

    return df_new


# ------------------------------------------------------------
# 🧪 Optional Standalone Test
# ------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    dummy = {
        "5m": pl.DataFrame(
            {
                "CMV": np.random.randn(5),
                "CMV_Bias": ["🟢"] * 5,
                "Regime_Emoji": ["🟢 Trend"] * 5,
                "Divergence_Signal": ["None"] * 5,
                "Liquidity_Trap": ["Inactive"] * 5,
                "Absorption_Zone": ["Stable"] * 5,
                "Squeeze_Signal": ["None"] * 5,
                "Exhaustion_Signal": ["➡️ Stable"] * 5,
                "Reversal_Alert": ["➡️ Stable"] * 5,
                "Reversal_Score": [1.2] * 5,
                "Reversal_Confidence": ["LOW"] * 5,
                "CMV_Flip": [False] * 5,
                "SPS": [0.3] * 5,
                "volume": [3500] * 5,
            }
        ),
        "1h": pl.DataFrame(
            {
                "CMV": np.random.randn(5),
                "CMV_Bias": ["🔻"] * 5,
                "Regime_Emoji": ["⚫ Neutral"] * 5,
                "Divergence_Signal": ["Bearish"] * 5,
                "Liquidity_Trap": ["Active"] * 5,
                "Absorption_Zone": ["Detected"] * 5,
                "Squeeze_Signal": ["Tight"] * 5,
                "Exhaustion_Signal": ["🟥 Bearish Exhaustion"] * 5,
                "Reversal_Alert": ["🔴 SELL Confluence"] * 5,
                "Reversal_Score": [3.8] * 5,
                "Reversal_Confidence": ["HIGH"] * 5,
                "CMV_Flip": [True] * 5,
                "SPS": [0.8] * 5,
                "volume": [4200] * 5,
            }
        ),
    }

    new_df = log_tactical_events(dummy)
    print("Logged Events:")
    print(new_df)
