# quant/signals/pre_breakout.py
# ------------------------------------------------------------
# Setup Pressure Scoring System (SPS)
# Detects pre-breakout compression, volume buildup, and latent momentum
# ------------------------------------------------------------

import numpy as np
import polars as pl
from quant import config
from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# ✅ Config Access — DRY via quant.config
# ============================================================
def load_config():
    """Load relevant configs (meta_layers, indicators, weights, formulas) via the central loader."""
    return {
        "meta_layers": config.get_section("meta_layers"),
        "weights": config.get_section("weights"),
        "formulas": config.get_section("formulas"),
        "indicators": config.get_section("indicators"),
        "timeframes": config.get_section("timeframes"),
    }


# ------------------------------------------------------------
# 🕒 Dynamic Timeframe Context Discovery
# ------------------------------------------------------------
def get_active_timeframes() -> list[str]:
    """Return a list of active timeframe keys from configs (meta_layers or timeframes)."""
    meta_cfg = config.get_section("meta_layers")
    tf_cfg = config.get_section("timeframes")

    if "SPS" in meta_cfg and "contexts" in meta_cfg["SPS"]:
        return list(meta_cfg["SPS"]["contexts"].keys())
    if "timeframes" in tf_cfg:
        return list(tf_cfg["timeframes"].keys())
    return ["intraday_15m"]


# ------------------------------------------------------------
# ⚙️ Pre-Breakout Computation
# ------------------------------------------------------------



def compute_pre_breakout(df: pl.DataFrame, timeframe: str = "daily") -> pl.DataFrame:
    """Compute pre-breakout setup pressure and CPR width with realistic Bollinger Bands.
    Self-healing version: handles missing BB, momentum, and SPS safely.
    """
    # ============================================================
    # 🧱 Step 1: Ensure required numeric columns exist
    # ============================================================
    core_cols = ["close", "high", "low", "volume"]
    for col in core_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # ============================================================
    # 🧮 Step 2: Build realistic Bollinger Bands if missing
    # ============================================================
    bb_required = {"bb_upper", "bb_lower", "bb_mid"}
    if not bb_required.issubset(set(df.columns)):
        lf = df.lazy()
        window = 20

        lf = lf.with_columns([
            pl.col("close").rolling_mean(window).alias("bb_mid"),
            (pl.col("close").rolling_mean(window) + 2 * pl.col("close").rolling_std(window)).alias("bb_upper"),
            (pl.col("close").rolling_mean(window) - 2 * pl.col("close").rolling_std(window)).alias("bb_lower"),
        ])
        df = lf.collect().fill_null(strategy="forward").fill_null(strategy="backward")

    # ============================================================
    # ⚙️ Step 3: CPR Width (volatility contraction)
    # ============================================================
    df = df.with_columns(
        ((pl.col("bb_upper") - pl.col("bb_lower")) / pl.col("bb_mid")).alias("cpr_width")
    )

    # ============================================================
    # 📊 Step 4: Setup Pressure Score (SPS)
    # ============================================================
    if "VPR" not in df.columns:
        df = df.with_columns(pl.lit(1.0).alias("VPR"))

    df = df.with_columns(
        (pl.col("VPR") * (1 / (1 + pl.col("cpr_width")))).alias("SPS")
    )

    # ============================================================
    # 🔍 Step 5: Momentum & Trend Context (split for Polars safety)
    # ============================================================
    # Step 5a: Compute momentum
    df = df.with_columns(
        (pl.col("close").diff()).alias("momentum")
    )

    # Step 5b: Compute rolling smoothed momentum
    df = df.with_columns(
        pl.col("momentum").rolling_mean(window_size=5).alias("momentum_smooth")
    )

    # Step 5c: Determine trend direction (uptrend flag)
    df = df.with_columns(
        ((pl.col("momentum_smooth") > 0).cast(pl.Int8)).alias("trend_up")
    )

    # ============================================================
    # 🧩 Step 6: Clean up any NaN / None
    # ============================================================
    df = df.fill_nan(None).fill_null(strategy="forward")
    return df


# ------------------------------------------------------------
# 🎨 Rich Summary (with gradient intensity)
# ------------------------------------------------------------
def print_pre_breakout_summary(df: pl.DataFrame, timeframe: str = "intraday_15m"):
    """Display summarized pre-breakout readings in Rich table with color intensity."""
    recent = df.tail(12)
    table = Table(title=f"⚡ SPS Heatmap — {timeframe.upper()}", expand=True)
    table.add_column("Timestamp", justify="left", style="cyan")
    table.add_column("SPS", justify="right", style="bold")
    table.add_column("CWI", justify="right")
    table.add_column("VPR", justify="right")
    table.add_column("ML", justify="right")
    table.add_column("OCD", justify="right")
    table.add_column("Alert", justify="center", style="yellow")

    for row in recent.iter_rows(named=True):
        sps = row.get("SPS", 0.0)
        color = (
            "red" if sps < 0.8
            else "yellow" if sps < 1.2
            else "green_yellow" if sps < 1.5
            else "bright_green"
        )
        table.add_row(
            str(row.get("timestamp", ""))[:16],
            f"[{color}]{sps:.2f}[/{color}]",
            f"{row.get('CWI', 0):.2f}",
            f"{row.get('VPR', 0):.2f}",
            f"{row.get('ML', 0):.2f}",
            f"{row.get('OCD', 0):.2f}",
            row.get("setup_alert", ""),
        )

    console.print(table)


# ------------------------------------------------------------
# 🧪 Example Usage
# ------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    n = 80
    df = pl.DataFrame({
        "timestamp": pl.datetime_range("2025-01-01", "2025-03-21", interval="1d"),
        "high": np.random.uniform(100, 120, n),
        "low": np.random.uniform(90, 100, n),
        "close": np.random.uniform(95, 115, n),
        "volume": np.random.randint(1000, 3000, n),
        "rsi_14": np.random.uniform(30, 70, n),
        "obv": np.cumsum(np.random.randint(-500, 500, n)),
        "bb_mid": np.random.uniform(100, 110, n),
        "bb_upper": np.random.uniform(110, 115, n),
        "bb_lower": np.random.uniform(95, 100, n),
        "atr_14": np.random.uniform(1.0, 2.5, n),
    })

    for tf in get_active_timeframes():
        console.rule(f"[bold green]⏱️ Processing {tf}")
        df_tf = compute_pre_breakout(df.clone(), timeframe=tf)
        print_pre_breakout_summary(df_tf, timeframe=tf)
