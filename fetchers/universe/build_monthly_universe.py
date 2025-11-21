#!/usr/bin/env python3
# ============================================================
# quant/engine/universe/build_monthly_universe.py — v1.2 (Forward-Compatible)
# ============================================================
"""Quant-Core v1.2 — Monthly Active Universe Builder (Async + DRY + Polars)
---------------------------------------------------------------------------
Reads:
    • master_active_list.json (from data_config)
    • universe_config.json (for weights & thresholds)
Writes:
    • monthly_active_universe.json (runtime)
    • /history/monthly_active_universe_<tag>.json
Features:
    ✅ 100% Config-driven (no hardcoded paths)
    ✅ Async concurrent fetch via FetchRouter
    ✅ Polars-native scoring & normalization
    ✅ Forward-only (no multifetch dependency)
    ✅ Consistent with LiveFeedDaemon v10.7 architecture
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json

import polars as pl
from quant import config
from quant.engine.fetchers.fetch_router import FetchRouter
from quant.utils.logs import auto_logger
from quant.utils.market import get_market_state
from quant.utils.scheduler import get_default_interval

logger = auto_logger("UniverseBuilder")

# ============================================================
# ⚙️ CONFIG BINDINGS
# ============================================================
UNIVERSE_DIR = config.get_path("paths.universe_dir")
MASTER_FILE = config.get_path("paths.master_active_list")
ACTIVE_FILE = config.get("files.monthly_active_universe")
BROKER = config.get("defaults.broker", "upstox")
INTERVAL = get_default_interval()

FACTORS = config.get(
    "factors", {"momentum": 0.4, "liquidity": 0.3, "volatility": 0.2, "trend": 0.1}
)
THRESHOLDS = config.get(
    "thresholds", {"min_turnover": 5e7, "min_price": 50, "max_rank": 300}
)


# ============================================================
# 🧠 Core Computation Helpers
# ============================================================
def normalize_series(s: pl.Series) -> pl.Series:
    if s.max() == s.min():
        return pl.Series(s.name, [0.5] * len(s))
    return (s - s.min()) / (s.max() - s.min())


def compute_factors(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort("timestamp")
    momentum = (
        ((df["close"][-1] - df["close"][0]) / df["close"][0] * 100)
        if len(df) > 1
        else 0
    )
    volatility = float(df["close"].std())
    liquidity = float((df["close"] * df["volume"]).mean())
    df = df.with_columns(pl.col("close").ewm_mean(span=10).alias("ema10"))
    trend = (df["ema10"][-1] - df["ema10"][0]) / len(df) if len(df) > 1 else 0
    return pl.DataFrame(
        {
            "momentum": [momentum],
            "volatility": [volatility],
            "liquidity": [liquidity],
            "trend": [trend],
        }
    )


def build_score(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        [
            normalize_series(pl.col("momentum")).alias("momentum_n"),
            normalize_series(pl.col("liquidity")).alias("liquidity_n"),
            (1 - normalize_series(pl.col("volatility"))).alias("volatility_n_inv"),
            normalize_series(pl.col("trend")).alias("trend_n"),
        ]
    )
    df = df.with_columns(
        (
            pl.col("momentum_n") * FACTORS["momentum"]
            + pl.col("liquidity_n") * FACTORS["liquidity"]
            + pl.col("volatility_n_inv") * FACTORS["volatility"]
            + pl.col("trend_n") * FACTORS["trend"]
        ).alias("score")
    )
    return df.sort("score", descending=True)


# ============================================================
# 🚀 Async Builder Logic (Router-based)
# ============================================================
async def build_universe():
    now = dt.datetime.now()
    ym_tag = now.strftime("%Y%m")
    logger.info(f"🚀 Building Monthly Universe {ym_tag}")

    # Load master symbols
    master_data = json.loads(MASTER_FILE.read_text())
    symbols = [x["symbol"] for x in master_data.get("data", [])]
    if not symbols:
        logger.error("❌ No symbols found in master_active_list.json")
        return
    logger.info(f"📦 Loaded {len(symbols)} master symbols")

    router = FetchRouter(BROKER)
    tasks = [router.get_candles(symbol, INTERVAL) for symbol in symbols]
    dfs = await asyncio.gather(*tasks, return_exceptions=True)
    await router.close()

    # Filter valid dataframes
    valid = [df for df in dfs if isinstance(df, pl.DataFrame) and not df.is_empty()]
    if not valid:
        logger.error("❌ No valid data fetched — aborting build.")
        return

    logger.info(f"✅ Received {len(valid)} valid datasets")

    # Compute per-symbol factors
    frames = []
    for df, symbol in zip(valid, symbols):
        try:
            fdf = compute_factors(df).with_columns(pl.lit(symbol).alias("symbol"))
            frames.append(fdf)
        except Exception as e:
            logger.warning(f"⚠️ Skipped {symbol}: {e}")

    combined = pl.concat(frames, how="diagonal")
    combined = build_score(combined)
    selected = combined.filter(
        (pl.col("liquidity") >= THRESHOLDS["min_turnover"]) & (pl.col("score") > 0)
    ).head(THRESHOLDS["max_rank"])

    meta = {
        "generated_at": now.isoformat(timespec="seconds"),
        "source": str(MASTER_FILE),
        "count_total": len(combined),
        "count_selected": len(selected),
        "weights": FACTORS,
        "state": get_market_state(),
    }

    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    history_dir = UNIVERSE_DIR / "history"
    history_dir.mkdir(exist_ok=True)

    active_path = UNIVERSE_DIR / ACTIVE_FILE
    history_path = history_dir / f"monthly_active_universe_{ym_tag}.json"

    payload = {"meta": meta, "data": selected.to_dicts()}
    active_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    history_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    logger.info(f"✅ Universe saved → {active_path.name}")
    logger.info(f"🗂️ Archived → {history_path.name}")
    logger.info(
        f"📊 {len(selected)} symbols selected (max_rank={THRESHOLDS['max_rank']})"
    )


# ============================================================
# 🧩 CLI Entry
# ============================================================
if __name__ == "__main__":
    asyncio.run(build_universe())
