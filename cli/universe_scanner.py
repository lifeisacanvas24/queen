#!/usr/bin/env python3
# ============================================================
# queen/cli/universe_scanner.py — v2.1 (Shareholding Integration)
# ============================================================
"""Production-grade NSE/BSE universe scanner with fundamental analysis"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from queen.fetchers.fetch_router import run_router
from queen.helpers.logger import log
from queen.helpers.nse_fetcher import fetch_nse_bands
from queen.helpers.shareholding_fetcher import get_complete_fundamentals
from queen.settings import settings as SETTINGS

# ============================================================
# ⚙️ CONFIGURATION
# ============================================================
PATHS = SETTINGS.PATHS
CACHE_DIR = PATHS["CACHE"] / "universe_scan"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- PRE-FILTER THRESHOLDS ---
MIN_AVG_DAILY_VALUE = 10_000_000  # ₹1 crore
MIN_LISTING_DAYS = 180
MIN_MARKET_CAP = 500_000_000  # ₹50 crore

# --- FUNDAMENTAL HARD FILTERS ---
MAX_PLEDGED_PCT = 50.0
MIN_PROMOTER_HOLDING = 20.0
MAX_DEBT_TO_EQUITY = 2.0

# --- SCORING WEIGHTS ---
INTRADAY_WEIGHTS = {
    "volatility": 0.20, "liquidity": 0.20, "spread_cost": 0.15,
    "beta": 0.15, "momentum": 0.10, "fundamentals": 0.20,
}

BTST_WEIGHTS = {
    "delivery": 0.20, "momentum": 0.15, "volatility": 0.15,
    "beta": 0.10, "liquidity": 0.15, "fundamentals": 0.25,
}

# --- IDEAL RANGES ---
IDEAL_RANGES = {
    "volatility_intraday": (2.0, 5.0), "volatility_btst": (1.5, 3.0),
    "liquidity": 150.0, "delivery_btst": 40.0, "delivery_intraday": 30.0,
    "spread_max": 0.05, "beta_intraday": (1.2, 1.8), "beta_btst": (0.8, 1.5),
    "momentum": (95.0, 105.0),
}


# ============================================================
# 🧹 PHASE 1: PRE-FILTERING (Illiquidity Removal)
# ============================================================
def load_and_prefilter_symbols(symbols_path: Path, max_symbols: Optional[int] = None) -> List[str]:
    """Load symbols from NSE master CSV and aggressively pre-filter"""
    log.info(f"[Phase 1] Loading symbols from {symbols_path.name}")

    # Read CSV
    df = pl.read_csv(symbols_path)

    # Basic filters
    df = df.filter(
        (pl.col("SERIES") == "EQ") &
        (pl.col("FACE_VALUE") > 0) &
        (pl.col("PAID UP VALUE") > 0)
    )

    # Listing date filter (seasoning)
    cutoff_date = datetime.now() - timedelta(days=MIN_LISTING_DAYS)
    df = df.filter(pl.col("DATE OF LISTING").str.to_date("%d-%b-%Y") <= cutoff_date)

    # Market cap proxy filter (paid-up value in lakhs)
    df = df.filter(pl.col("PAID UP VALUE") >= MIN_MARKET_CAP / 1_000_000)

    log.info(f"[Phase 1] {len(df)} symbols after pre-filtering")

    return df["SYMBOL"].head(max_symbols).to_list()


# ============================================================
# 🧮 PHASE 2: TECHNICAL CALCULATIONS
# ============================================================
def calculate_volatility(df: pl.DataFrame) -> Optional[float]:
    """20-day ATR%"""
    if df.is_empty() or len(df) < 20:
        return None
    df = df.with_columns(
        tr=pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("close").shift(1)).abs(),
            (pl.col("low") - pl.col("close").shift(1)).abs(),
        )
    )
    atr = df.select(pl.col("tr").rolling_mean(14).tail(1).first())["tr"].item()
    close = df.select(pl.col("close").tail(1).first())["close"].item()
    return (atr / close) * 100 if close else None


def calculate_liquidity_score(df: pl.DataFrame, avg_volume: float) -> Optional[float]:
    """Recent volume vs 20-day average"""
    if df.is_empty() or avg_volume == 0:
        return None
    recent_avg = df.select(pl.col("volume").tail(5).mean())["volume"].item()
    return (recent_avg / avg_volume) * 100


def calculate_momentum_score(df: pl.DataFrame) -> Optional[float]:
    """Current price vs 50-EMA (100 = neutral)"""
    if df.is_empty() or len(df) < 50:
        return None
    df = df.with_columns(ema_50=pl.col("close").ewm_mean(span=50))
    current = df.select(pl.col("close").tail(1).first())["close"].item()
    ema = df.select(pl.col("ema_50").tail(1).first())["ema_50"].item()
    return (current / ema) * 100 if ema else None


def calculate_beta(df: pl.DataFrame, nifty_df: pl.DataFrame) -> Optional[float]:
    """Beta vs Nifty 50 (20-day)"""
    if df.is_empty() or nifty_df.is_empty() or len(df) < 20:
        return None

    merged = df.join(nifty_df, on="timestamp", how="inner", suffix="_nifty")
    if merged.is_empty():
        return None

    merged = merged.with_columns(
        returns=(pl.col("close") / pl.col("close").shift(1) - 1),
        returns_nifty=(pl.col("close_nifty") / pl.col("close_nifty").shift(1) - 1),
    ).drop_nulls()

    if merged.is_empty():
        return None

    cov = merged.select(pl.cov(pl.col("returns"), pl.col("returns_nifty")))["returns"][0]
    var_nifty = merged.select(pl.col("returns_nifty").var())["returns_nifty"].item()
    return cov / var_nifty if var_nifty else None


def calculate_spread_cost(df: pl.DataFrame) -> Optional[float]:
    """Intraday spread cost proxy using OHLC"""
    if df.is_empty():
        return None
    spread = df.select(((pl.col("high") - pl.col("low")) / pl.col("close")).mean())["high"].item()
    return spread * 100


def get_delivery_percentage(symbol: str, hist_df: pl.DataFrame) -> Optional[float]:
    """Delivery percentage (proxy - replace with real NSE data)"""
    # TODO: Integrate with NSE delivery data API:
    # https://www.nseindia.com/api/sym-deliverables?symbol={symbol}&series=EQ
    return 35.0


def score_parameter(value: Optional[float], ideal_range: tuple) -> float:
    """Score 0-10 based on proximity to ideal range"""
    if value is None:
        return 0.0
    min_val, max_val = ideal_range
    if min_val <= value <= max_val:
        return 10.0
    # Linear decay
    if value < min_val:
        return max(0.0, 10.0 - (min_val - value) / min_val * 10)
    return max(0.0, 10.0 - (value - max_val) / max_val * 10)


# ============================================================
# 💼 PHASE 3: FUNDAMENTAL SCORING
# ============================================================
def score_fundamentals(fundamentals: Dict[str, Any]) -> float:
    """Score fundamentals 0-10 for trading suitability"""
    if not fundamentals:
        return 0.0

    score = 0.0

    # Market cap score (stability)
    mcap = fundamentals.get("market_cap", 0)
    if mcap >= 10_000:  # ₹10,000 cr
        score += 3.0
    elif mcap >= 1_000:  # ₹1,000 cr
        score += 2.0
    elif mcap >= 500:   # ₹500 cr min
        score += 1.0

    # Pledged shares (lower is better)
    pledged = fundamentals.get("pledged_percentage", 100)
    if pledged <= 20:
        score += 2.5
    elif pledged <= 50:
        score += 1.0

    # Promoter holding (sweet spot: 30-75%)
    promoter = fundamentals.get("promoter_holding", 0)
    if 30 <= promoter <= 75:
        score += 2.0
    elif 20 <= promoter < 30:
        score += 1.0
    else:
        score += 0.5

    # Debt-to-equity (low is good for BTST)
    debt_ratio = fundamentals.get("debt_to_equity", 10)
    if debt_ratio <= 0.5:
        score += 2.0
    elif debt_ratio <= 1.0:
        score += 1.5
    elif debt_ratio <= 2.0:
        score += 0.5

    # FII/DII ownership (institutional confidence)
    fii = fundamentals.get("fii_holding", 0)
    dii = fundamentals.get("dii_holding", 0)
    institutional = fii + dii

    if institutional >= 25:
        score += 0.5

    return min(10.0, score)


# ============================================================
# 🎯 PHASE 4: COMPLETE SYMBOL SCAN
# ============================================================
async def scan_symbol(
    symbol: str,
    nifty_df: pl.DataFrame,
    from_date: str,
    to_date: str,
) -> Optional[Dict[str, Any]]:
    """Complete scan: technical + fundamental analysis"""
    log.info(f"[Scanner] Processing {symbol}")

    # --- TECHNICAL DATA ---
    hist_df = await run_router(
        [symbol], mode="daily", from_date=from_date, to_date=to_date, interval="1d"
    )
    if hist_df is None or hist_df.is_empty():
        log.warning(f"[Scanner] No historical data for {symbol}")
        return None

    # Re-verify liquidity
    avg_daily_value = hist_df.select(
        (pl.col("close") * pl.col("volume")).mean()
    )["close"].item() or 0

    if avg_daily_value < MIN_AVG_DAILY_VALUE:
        log.info(f"[Scanner] {symbol} rejected: avg value ₹{avg_daily_value:,.0f} < threshold")
        return None

    # Intraday for spread
    intra_start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    intra_df = await run_router(
        [symbol], mode="intraday", from_date=intra_start, to_date=to_date, interval="5m"
    )

    # --- FUNDAMENTALS ---
    fundamentals = await get_complete_fundamentals(symbol)
    if not fundamentals:
        log.warning(f"[Scanner] No fundamental data for {symbol}, skipping")
        return None

    # Apply fundamental hard filters
    if fundamentals.get("pledged_percentage", 0) > MAX_PLEDGED_PCT:
        log.info(f"[Scanner] {symbol} rejected: pledged {fundamentals['pledged_percentage']}% > {MAX_PLEDGED_PCT}%")
        return None

    if fundamentals.get("promoter_holding", 0) < MIN_PROMOTER_HOLDING:
        log.info(f"[Scanner] {symbol} rejected: promoter {fundamentals['promoter_holding']}% < {MIN_PROMOTER_HOLDING}%")
        return None

    if fundamentals.get("debt_to_equity", 10) > MAX_DEBT_TO_EQUITY:
        log.info(f"[Scanner] {symbol} rejected: D/E {fundamentals['debt_to_equity']} > {MAX_DEBT_TO_EQUITY}")
        return None

    # Score fundamentals
    fundamental_score = score_fundamentals(fundamentals)

    # --- TECHNICAL METRICS ---
    metrics = {
        "volatility": calculate_volatility(hist_df),
        "liquidity": calculate_liquidity_score(hist_df, hist_df["volume"].mean()),
        "momentum": calculate_momentum_score(hist_df),
        "beta": calculate_beta(hist_df, nifty_df),
        "spread_cost": calculate_spread_cost(intra_df) if not intra_df.is_empty() else None,
        "delivery": get_delivery_percentage(symbol, hist_df),
        "current_price": hist_df.select(pl.col("close").tail(1).first())["close"].item(),
        "avg_volume": hist_df.select(pl.col("volume").mean())["volume"].item(),
    }

    # Circuit limits
    bands = fetch_nse_bands(symbol)

    # --- SCORING ---
    tech_scores = {
        "volatility": score_parameter(metrics["volatility"], IDEAL_RANGES["volatility_intraday"]),
        "liquidity": min(10.0, (metrics["liquidity"] or 0) / IDEAL_RANGES["liquidity"] * 10),
        "spread_cost": max(0.0, 10.0 - (metrics["spread_cost"] or 100) / IDEAL_RANGES["spread_max"]),
        "beta": score_parameter(metrics["beta"], IDEAL_RANGES["beta_intraday"]),
        "momentum": score_parameter(metrics["momentum"], IDEAL_RANGES["momentum"]),
    }

    # Intraday score
    intraday_tech_score = sum(tech_scores[k] * INTRADAY_WEIGHTS[k] for k in tech_scores) * 10
    intraday_score = intraday_tech_score * 0.8 + fundamental_score * 2.0

    # BTST score
    btst_scores = {
        "delivery": min(10.0, (metrics["delivery"] or 0) / IDEAL_RANGES["delivery_btst"] * 10),
        "momentum": tech_scores["momentum"],
        "volatility": score_parameter(metrics["volatility"], IDEAL_RANGES["volatility_btst"]),
        "beta": score_parameter(metrics["beta"], IDEAL_RANGES["beta_btst"]),
        "liquidity": tech_scores["liquidity"],
    }
    btst_tech_score = sum(btst_scores[k] * BTST_WEIGHTS[k] for k in btst_scores) * 10
    btst_score = btst_tech_score * 0.75 + fundamental_score * 2.5

    # Tier classification
    tier = "Exclude"
    if intraday_score >= 75:
        tier = "Tier 1: Intraday Core"
    elif btst_score >= 70:
        tier = "Tier 2: BTST Core"
    elif max(intraday_score, btst_score) >= 60:
        tier = "Tier 3: Mixed"

    return {
        "symbol": symbol,
        "tier": tier,
        "intraday_score": round(intraday_score, 2),
        "btst_score": round(btst_score, 2),
        "fundamental_score": round(fundamental_score, 2),
        "metrics": {k: round(v, 3) if isinstance(v, float) else v for k, v in metrics.items()},
        "fundamentals": fundamentals,
        "circuit_limits": bands,
        "last_updated": datetime.now().isoformat(),
    }


# ============================================================
# 🚀 MAIN ORCHESTRATOR
# ============================================================
async def main(
    symbols_path: Path,
    output_dir: Path,
    max_symbols: Optional[int] = None,
    concurrency: int = 5,
) -> None:
    """Complete end-to-end scan"""
    start_time = datetime.now()
    log.info("=" * 70)
    log.info(f"UNIVERSE SCAN STARTED AT {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 70)

    # Phase 1: Pre-filter
    symbols = load_and_prefilter_symbols(symbols_path, max_symbols)

    # Phase 2: Benchmark data
    today = datetime.now()
    from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    log.info(f"[Phase 2] Fetching Nifty 50 baseline")
    nifty_df = await run_router(
        ["NIFTY50"], mode="daily", from_date=from_date, to_date=to_date, interval="1d"
    )
    if nifty_df is None or nifty_df.is_empty():
        log.error("[Scanner] Failed to fetch Nifty 50")
        return

    # Phase 3: Scan with concurrency
    log.info(f"[Phase 3] Scanning {len(symbols)} symbols with concurrency={concurrency}")
    tasks = [scan_symbol(s, nifty_df, from_date, to_date) for s in symbols]
    results = await asyncio.gather(*tasks)
    results = [r for r in results if r is not None]

    # Phase 4: Save results
    results_df = pl.DataFrame(results)
    timestamp = today.strftime("%Y%m%d_%H%M")

    # Full parquet
    full_path = output_dir / f"universe_scan_{timestamp}.parquet"
    results_df.write_parquet(full_path)
    log.info(f"[Output] Full results → {full_path}")

    # Tiered CSVs with flattened columns
    for tier_name in ["Tier 1: Intraday Core", "Tier 2: BTST Core", "Tier 3: Mixed"]:
        tier_df = results_df.filter(pl.col("tier") == tier_name)
        if not tier_df.is_empty():
            csv_path = output_dir / f"{tier_name.replace(':', '').replace(' ', '_').lower()}_{today.strftime('%Y%m%d')}.csv"

            # Flatten for readability
            csv_df = tier_df.select([
                "symbol",
                "intraday_score",
                "btst_score",
                "fundamental_score",
                pl.col("metrics").struct.field("volatility").alias("volatility_pct"),
                pl.col("metrics").struct.field("liquidity").alias("liquidity_pct"),
                pl.col("metrics").struct.field("beta").alias("beta"),
                pl.col("metrics").struct.field("current_price").alias("price"),
                pl.col("metrics").struct.field("avg_volume").alias("avg_volume"),
                pl.col("metrics").struct.field("avg_daily_value").alias("avg_daily_value"),
                pl.col("fundamentals").struct.field("market_cap").alias("market_cap_cr"),
                pl.col("fundamentals").struct.field("pledged_percentage").alias("pledged_pct"),
                pl.col("fundamentals").struct.field("promoter_holding").alias("promoter_pct"),
                pl.col("fundamentals").struct.field("fii_holding").alias("fii_pct"),
                pl.col("fundamentals").struct.field("dii_holding").alias("dii_pct"),
                pl.col("circuit_limits").struct.field("upper_circuit").alias("upper_circuit"),
                pl.col("circuit_limits").struct.field("lower_circuit").alias("lower_circuit"),
            ])

            csv_df.write_csv(csv_path)
            log.info(f"[Output] {tier_name} → {csv_path} ({len(csv_df)} symbols)")

    # Summary
    summary = results_df.groupby("tier").agg([
        pl.count().alias("count"),
        pl.col("intraday_score").mean().alias("avg_intraday_score"),
        pl.col("btst_score").mean().alias("avg_btst_score"),
        pl.col("fundamental_score").mean().alias("avg_fundamental_score"),
    ]).sort("tier")

    log.info("\n" + "=" * 70)
    log.info("SCAN SUMMARY")
    log.info("=" * 70)
    for row in summary.iter_rows(named=True):
        log.info(
            f"{row['tier']:<25} | Count: {row['count']:>3} | "
            f"Avg Intraday: {row['avg_intraday_score']:>5.1f} | "
            f"Avg BTST: {row['avg_btst_score']:>5.1f} | "
            f"Avg Fundamentals: {row['avg_fundamental_score']:>5.1f}"
        )

    # Top symbols
    tier1 = results_df.filter(pl.col("tier") == "Tier 1: Intraday Core")["symbol"].to_list()
    tier2 = results_df.filter(pl.col("tier") == "Tier 2: BTST Core")["symbol"].to_list()

    log.info("\n" + "=" * 70)
    log.info("TOP RECOMMENDATIONS")
    log.info("=" * 70)
    log.info(f"Tier 1 (Intraday): {', '.join(tier1[:15])}")
    log.info(f"Tier 2 (BTST): {', '.join(tier2[:15])}")

    duration = (datetime.now() - start_time).total_seconds()
    log.info(f"\n[Scanner] Completed in {duration:.1f} seconds ({len(results)} symbols passed)")


# ============================================================
# ⏰ CLI INTERFACE
# ============================================================
def run_cli():
    parser = argparse.ArgumentParser(
        description="End-to-end NSE/BSE universe scanner with fundamentals",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--symbols", required=True, help="Path to NSE master CSV")
    parser.add_argument("--output", default=CACHE_DIR, help="Output directory")
    parser.add_argument("--max", type=int, metavar="N", help="Max symbols for testing")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent scans")
    parser.add_argument("--force-refresh", action="store_true", help="Clear fundamental cache")
    args = parser.parse_args()

    if args.force_refresh:
        cache_file = CACHE_DIR / "fundamentals.json"
        if cache_file.exists():
            cache_file.unlink()
            log.info("[CLI] Fundamental cache cleared")

    asyncio.run(main(Path(args.symbols), Path(args.output), args.max, args.concurrency))


if __name__ == "__main__":
    run_cli()
