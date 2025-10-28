# ============================================================
# queen/technicals/signals/tactical/exhaustion.py
# ------------------------------------------------------------
# ⚡ Tactical Exhaustion Bar Detector (Phase 4.7)
# Detects exhaustion candles — high volume spikes,
# long wicks, and CMV momentum collapse at trend ends.
# ============================================================

import numpy as np
import polars as pl


def detect_exhaustion_bars(
    df: pl.DataFrame,
    cmv_col: str = "CMV",
    volume_col: str = "volume",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    lookback_vol: int = 20,
    wick_threshold: float = 0.6,
    cmv_drop: float = 0.4,
) -> pl.DataFrame:
    """Detects exhaustion bars where:
      • volume spike > rolling mean × 1.5
      • wick size ≥ wick_threshold × body
      • CMV momentum drop ≥ cmv_drop

    Adds columns:
        Volume_Spike, Wick_Ratio, CMV_Delta, Exhaustion_Signal
    """
    df = df.clone()

    # --- Safety checks ---
    required = [cmv_col, volume_col, high_col, low_col, close_col]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # --- Compute volume spike ratio (float-safe, API-safe) ---
    vol = np.array(df[volume_col].fill_null(0).to_numpy(), dtype=float)
    try:
        vol_ma = np.array(
            df.select(pl.col(volume_col).rolling_mean(window_size=lookback_vol))
            .to_series()
            .fill_null(0)
            .to_numpy(),
            dtype=float,
        )
    except TypeError:
        # Backward compatibility with older Polars (<1.5)
        vol_ma = np.array(
            df.select(pl.col(volume_col).rolling_mean(window=lookback_vol))
            .to_series()
            .fill_null(0)
            .to_numpy(),
            dtype=float,
        )

    with np.errstate(divide="ignore", invalid="ignore"):
        vol_spike = np.where(vol_ma != 0, vol / vol_ma, 1.0)

    # --- Candle wick ratio ---
    high = np.array(df[high_col].to_numpy(), dtype=float)
    low = np.array(df[low_col].to_numpy(), dtype=float)
    close = np.array(df[close_col].to_numpy(), dtype=float)

    candle_range = np.maximum(high - low, 1e-6)
    body = np.abs(close - (high + low) / 2)
    wick_size = candle_range - body
    wick_ratio = np.where(body != 0, wick_size / (body + 1e-6), 0.0)

    # --- CMV momentum delta ---
    cmv = np.array(df[cmv_col].fill_null(0).to_numpy(), dtype=float)
    cmv_delta = np.insert(np.diff(cmv), 0, 0)

    # --- Detection logic ---
    signals = np.full(len(df), "➡️ Stable", dtype=object)
    for i in range(lookback_vol, len(df)):
        if vol_spike[i] < 1.5:
            continue
        if wick_ratio[i] < wick_threshold:
            continue
        if abs(cmv_delta[i]) < cmv_drop:
            continue

        if cmv[i] > 0 and cmv_delta[i] < 0:
            signals[i] = "🟥 Bearish Exhaustion"
        elif cmv[i] < 0 and cmv_delta[i] > 0:
            signals[i] = "🟩 Bullish Exhaustion"

    # --- Attach results ---
    df = df.with_columns(
        [
            pl.Series("Volume_Spike", vol_spike),
            pl.Series("Wick_Ratio", wick_ratio),
            pl.Series("CMV_Delta", cmv_delta),
            pl.Series("Exhaustion_Signal", signals),
        ]
    )

    return df


# ----------------------------------------------------------------------
# 🧪 Stand-alone test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    n = 120
    np.random.seed(42)
    df = pl.DataFrame(
        {
            "high": np.random.uniform(100, 110, n),
            "low": np.random.uniform(95, 105, n),
            "close": np.random.uniform(97, 108, n),
            "volume": np.random.randint(1000, 5000, n),
            "CMV": np.random.uniform(-1, 1, n),
        }
    )

    result = detect_exhaustion_bars(df)
    print(
        result.select(
            ["volume", "Volume_Spike", "Wick_Ratio", "CMV_Delta", "Exhaustion_Signal"]
        ).tail(10)
    )
