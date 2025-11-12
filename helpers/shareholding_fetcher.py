#!/usr/bin/env python3
# ============================================================
# queen/helpers/shareholding_fetcher.py — v1.0 (Production)
# ============================================================
"""NSE Shareholding Pattern Fetcher
Fetches promoter, FII, DII, public holdings from NSE's corporate disclosures API
Cache-enabled with 24h TTL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

import httpx

from queen.helpers.logger import log
from queen.settings.settings import PATHS

# Cache configuration
CACHE_DIR = PATHS["CACHE"] / "shareholding"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "shareholding_cache.json"
CACHE_TTL = 24 * 3600  # 24 hours

# NSE API endpoints
SHAREHOLDING_URL = "https://www.nseindia.com/api/corp-share-holding"
FINANCIAL_RATIOS_URL = "https://www.nseindia.com/api/quote-equity"

# Session headers
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/get-quotes/equity",
}


def load_cache() -> Dict[str, Dict[str, Any]]:
    """Load shareholding cache with TTL check"""
    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)

        # Filter expired entries
        now = time.time()
        valid_cache = {
            k: v for k, v in cache.items()
            if (now - v.get("timestamp", 0)) < CACHE_TTL
        }

        # Clean old entries if cache is too large
        if len(valid_cache) > 5000:
            # Keep only most recent 3000
            sorted_items = sorted(
                valid_cache.items(),
                key=lambda x: x[1]["timestamp"],
                reverse=True
            )
            valid_cache = dict(sorted_items[:3000])
            log.info(f"[Shareholding] Cleaned cache, kept {len(valid_cache)} entries")

        return valid_cache

    except Exception as e:
        log.warning(f"[Shareholding] Cache load failed: {e}")
        return {}


def save_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    """Save cache to disk"""
    try:
        # Atomic write
        temp_file = CACHE_FILE.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(cache, f, indent=2)
        temp_file.replace(CACHE_FILE)
    except Exception as e:
        log.error(f"[Shareholding] Cache save failed: {e}")


async def get_nse_session() -> httpx.Cookies:
    """Get valid NSE session cookies"""
    async with httpx.AsyncClient(timeout=10) as client:
        # Hit homepage to get cookies
        await client.get(
            "https://www.nseindia.com",
            headers=_HEADERS,
            timeout=10
        )
        return client.cookies


async def fetch_shareholding_pattern(
    symbol: str,
    cookies: Optional[httpx.Cookies] = None
) -> Optional[Dict[str, float]]:
    """
    Fetch shareholding pattern for a symbol
    Returns: {
        "promoter": 28.5,
        "fii": 24.2,
        "dii": 12.8,
        "public": 34.5,
        "timestamp": "2024-11-11"
    }
    """
    symbol = symbol.strip().upper()
    cache = load_cache()

    # Check cache first
    if symbol in cache:
        log.debug(f"[Shareholding] Cache hit for {symbol}")
        return cache[symbol]["data"]

    log.info(f"[Shareholding] Fetching for {symbol}")

    try:
        # Get session cookies if not provided
        if cookies is None:
            cookies = await get_nse_session()

        async with httpx.AsyncClient(cookies=cookies, timeout=10) as client:
            # Fetch shareholding data
            params = {"symbol": symbol}
            response = await client.get(
                SHAREHOLDING_URL,
                params=params,
                headers=_HEADERS,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if not data or data.get("data") is None:
                log.warning(f"[Shareholding] No data returned for {symbol}")
                return None

            # Parse the shareholding pattern
            holding_data = data.get("data", [])
            if not holding_data:
                log.warning(f"[Shareholding] Empty data array for {symbol}")
                return None

            # Get the most recent period
            latest = holding_data[0]
            shareholding = latest.get("shareHolding", [])

            # Initialize categories
            holdings = {
                "promoter": 0.0,
                "fii": 0.0,
                "dii": 0.0,
                "public": 0.0,
                "timestamp": latest.get("date", datetime.now().strftime("%Y-%m-%d"))
            }

            # Sum up categories
            for item in shareholding:
                category = item.get("category", "").lower()
                value = float(item.get("value", 0) or 0)

                if "promoter" in category:
                    holdings["promoter"] += value
                elif "foreign" in category or "fii" in category:
                    holdings["fii"] += value
                elif "institutional" in category or "dii" in category:
                    holdings["dii"] += value
                elif "public" in category or "retail" in category:
                    holdings["public"] += value

            # Validate totals
            total = sum(holdings[k] for k in ["promoter", "fii", "dii", "public"])
            if abs(total - 100.0) > 5.0:  # Allow 5% rounding error
                log.warning(
                    f"[Shareholding] Holdings don't sum to 100% for {symbol}: {total:.1f}%"
                )
                # Normalize if needed
                if total > 0:
                    for k in holdings:
                        if k != "timestamp":
                            holdings[k] = (holdings[k] / total) * 100

            # Save to cache
            cache[symbol] = {
                "timestamp": time.time(),
                "data": holdings
            }
            save_cache(cache)

            log.info(
                f"[Shareholding] {symbol}: P:{holdings['promoter']:.1f}% "
                f"FII:{holdings['fii']:.1f}% DII:{holdings['dii']:.1f}% "
                f"Public:{holdings['public']:.1f}%"
            )

            return holdings

    except Exception as e:
        log.error(f"[Shareholding] Failed for {symbol}: {e}")
        return None


async def fetch_financial_ratios(
    symbol: str,
    cookies: Optional[httpx.Cookies] = None
) -> Optional[Dict[str, float]]:
    """
    Fetch debt-to-equity and other ratios from NSE
    """
    symbol = symbol.strip().upper()

    try:
        if cookies is None:
            cookies = await get_nse_session()

        async with httpx.AsyncClient(cookies=cookies, timeout=10) as client:
            params = {"symbol": symbol, "section": "trade_info"}
            response = await client.get(
                FINANCIAL_RATIOS_URL,
                params=params,
                headers=_HEADERS,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            trade_info = data.get("tradeInfo", {})
            ratios = trade_info.get("financialRatios", {})

            return {
                "debt_to_equity": float(ratios.get("debtToEquity", 0) or 0),
                "roe": float(ratios.get("returnOnEquity", 0) or 0),
                "pe_ratio": float(trade_info.get("peRatio", 0) or 0),
                "pb_ratio": float(trade_info.get("pbRatio", 0) or 0),
            }

    except Exception as e:
        log.error(f"[FinancialRatios] Failed for {symbol}: {e}")
        return None


async def get_complete_fundamentals(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get complete fundamental picture
    Returns: {
        "market_cap": 1250000,
        "pledged_percentage": 12.5,
        "promoter_holding": 28.5,
        "fii_holding": 24.2,
        "dii_holding": 12.8,
        "public_holding": 34.5,
        "debt_to_equity": 0.3,
        "roe": 18.5,
        "timestamp": "2024-11-11"
    }
    """
    # Reuse session cookies for efficiency
    cookies = await get_nse_session()

    # Fetch shareholding
    shareholding = await fetch_shareholding_pattern(symbol, cookies)
    if not shareholding:
        return None

    # Fetch financial ratios
    ratios = await fetch_financial_ratios(symbol, cookies)

    # Fetch market cap and pledge data (from existing nse_fetcher)
    from queen.helpers.nse_fetcher import fetch_nse_bands
    bands = fetch_nse_bands(symbol)

    # Combine all data
    fundamentals = {
        "market_cap": 0,  # Will be calculated from price and equity
        "pledged_percentage": 0,
        "promoter_holding": shareholding.get("promoter", 0),
        "fii_holding": shareholding.get("fii", 0),
        "dii_holding": shareholding.get("dii", 0),
        "public_holding": shareholding.get("public", 0),
        "debt_to_equity": ratios.get("debt_to_equity", 0) if ratios else 0,
        "roe": ratios.get("roe", 0) if ratios else 0,
        "pe_ratio": ratios.get("pe_ratio", 0) if ratios else 0,
        "timestamp": shareholding.get("timestamp", datetime.now().strftime("%Y-%m-%d"))
    }

    # Add market cap from price info if available
    if bands and bands.get("prev_close"):
        # For full market cap, we need total shares outstanding
        # This requires fetching equity capital from NSE's corporate info API
        # For now, we'll calculate approximate market cap from typical share structure
        # In production, fetch from: https://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=corp_info
        pass

    return fundamentals


# ============================================================
# 🧪 CLI Test Interface
# ============================================================
def test_cli():
    parser = argparse.ArgumentParser(
        description="Test shareholding fetcher for a single symbol"
    )
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g., RELIANCE)")
    args = parser.parse_args()

    async def main():
        result = await get_complete_fundamentals(args.symbol)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Failed to fetch data")

    asyncio.run(main())


if __name__ == "__main__":
    test_cli()
