#!/usr/bin/env python3
# ============================================================
# queen/fetchers/fundamentals_scraper.py — v3.2 (FINAL)
# Full Screener Scraper matching final scope.
# ============================================================
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup as BS, Tag

# Placeholder imports (assume they exist in the project)
from queen.settings.settings import FETCH, EXTERNAL_APIS
from queen.settings.fundamentals_map import SCREENER_FIELDS
# from queen.helpers.logger import log # Assume log is available
class Logger:
    def info(self, msg): print(msg)
    def warning(self, msg): print(msg)
    def error(self, msg): print(msg)
log = Logger()

# ------------------------------------------------------------
# Load settings
# ------------------------------------------------------------
S = FETCH.get("FUNDAMENTALS", {})
RAW_DIR = Path(S.get("RAW_DIR", Path("data/raw")))
PROCESSED_DIR = Path(S.get("PROCESSED_DIR", Path("data/processed")))
BASE_URL = S.get("BASE_URL", "https://www.screener.in/company/")

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Core Extraction Helpers
# ------------------------------------------------------------
def _extract_text_data(soup: BS) -> Dict[str, Any]:
    output = {}

    # 1. About
    about_div = soup.find("div", class_="company-info")
    if about_div:
        output["about"] = about_div.find("p").get_text(strip=True) if about_div.find("p") else None

    # 2. Key Points / Pros / Cons (Usually lists or paragraphs)
    for key in ["key_points", "pros", "cons"]:
        section = soup.find("section", id=key)
        if section:
            # Look for structured list items
            items = [li.get_text(strip=True) for li in section.find_all("li")]
            if items:
                output[key] = items

    return output


def _extract_top_ratios(soup: BS) -> Dict[str, Any]:
    output = {}
    ratios_div = soup.find("div", class_="company-ratios")
    if not ratios_div:
        return {}

    # This is a fixed structure of 10-12 divs/spans
    for span in ratios_div.find_all("span", class_="name"):
        key = span.get_text(strip=True).lower().replace(' ', '').replace('/', '')
        value_tag = span.find_next_sibling("span", class_="value")
        if value_tag:
            value = value_tag.get_text(strip=True)
            # Map key to internal schema and save original value (schema will coerce)
            for screener_key, internal_key in SCREENER_FIELDS["top_ratios"].items():
                if key == screener_key:
                    if isinstance(internal_key, str):
                        output[internal_key] = value
                    elif isinstance(internal_key, list) and len(internal_key) == 2:
                         # Handle high/low 52w which might be "100.0 / 50.0"
                         if '/' in value:
                             try:
                                 high, low = [x.strip() for x in value.split('/')]
                                 output[internal_key[0]] = high
                                 output[internal_key[1]] = low
                             except:
                                 pass
                    break

    return output


def _extract_table(soup: BS, table_id: str) -> Dict[str, Any]:
    # Handles quarters, P&L, BS, Cash Flow
    output: Dict[str, Dict[str, Any]] = {}
    table_tag = soup.find("section", id=table_id).find("table") if soup.find("section", id=table_id) else None
    if not table_tag:
        return {}

    rows = table_tag.find_all("tr")
    if not rows:
        return {}

    # Extract column headers (periods) from the first row
    period_cols = [th.get_text(strip=True) for th in rows[0].find_all("th")][1:]

    # Process data rows
    for row in rows[1:]:
        cols = row.find_all(["td", "th"])
        if not cols:
            continue

        row_key = cols[0].get_text(strip=True)
        series = {}
        for i, col in enumerate(cols[1:]):
            if i < len(period_cols):
                series[period_cols[i]] = col.get_text(strip=True)

        if row_key and series:
            output[row_key] = series

    return output


def _extract_flat_metrics(soup: BS, table_id: str) -> Dict[str, Any]:
    # Handles 'Ratios' and 'Growth' blocks which are usually structured as key:value pairs
    output = {}
    section = soup.find("section", id=table_id)
    table_tag = section.find("table") if section and section.find("table") else None

    if not table_tag:
        return {}

    # These tables typically have <tr> with key in <td>[0] and value in <td>[1]
    rows = table_tag.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            key_raw = cols[0].get_text(strip=True)
            value_raw = cols[1].get_text(strip=True)

            # Map and save
            key_map = SCREENER_FIELDS.get(table_id) or {}
            for screener_key, internal_key in key_map.items():
                # Simple loose matching on normalized keys
                if key_raw.lower().replace(' ', '').replace('%', '') == screener_key.lower().replace(' ', '').replace('%', ''):
                    output[internal_key] = value_raw
                    break

    return output


def _extract_shareholding(soup: BS) -> Dict[str, Any]:
    # Handles Shareholding table (time-series for multiple categories)
    output: Dict[str, Dict[str, Dict[str, str]]] = {"quarterly": {}, "yearly": {}}

    # Assuming only the main quarterly table is scraped for now (as it's the most common)
    table_tag = soup.find("section", id="shareholding").find("table") if soup.find("section", id="shareholding") else None
    if not table_tag:
        return output

    rows = table_tag.find_all("tr")
    if not rows:
        return output

    # Extract headers (periods) from the first row
    period_cols = [th.get_text(strip=True) for th in rows[0].find_all("th")][1:]

    for row in rows[1:]:
        cols = row.find_all(["td", "th"])
        if not cols:
            continue

        row_key_raw = cols[0].get_text(strip=True)
        # We need a stable key: Promoter, FII, DII, Public
        if row_key_raw.startswith("Promoters"):
            row_key = "promoters"
        elif row_key_raw.startswith("FIIs"):
            row_key = "fii"
        elif row_key_raw.startswith("DIIs"):
            row_key = "dii"
        elif row_key_raw.startswith("Public"):
            row_key = "public"
        else:
            continue

        series = {}
        for i, col in enumerate(cols[1:]):
            if i < len(period_cols):
                series[period_cols[i]] = col.get_text(strip=True)

        if series:
            # Assuming the main table is quarterly data
            output["quarterly"][row_key] = series

    return output


# ------------------------------------------------------------
# Main Extraction Logic
# ------------------------------------------------------------
def extract_fundamentals(symbol: str) -> Dict[str, Any]:
    symbol = symbol.upper()
    url = f"{BASE_URL}{symbol}/"

    try:
        session = requests.Session()
        r = session.get(url, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error(f"[FUNDAMENTALS] HTTP Error for {symbol}: {e}")
        return {}

    soup = BS(r.content, "html.parser")
    output: Dict[str, Any] = {"symbol": symbol}

    # Extract metadata (sector/date)
    sector_tag = soup.find("a", href=lambda href: href and href.startswith("/sector/"))
    output["sector"] = sector_tag.get_text(strip=True) if sector_tag else None

    update_tag = soup.find("div", class_="company-info").find("p", string=lambda t: t and "Last Updated" in t) if soup.find("div", class_="company-info") else None
    output["last_updated_date"] = update_tag.get_text(strip=True).split(":")[-1].strip() if update_tag else None

    # Core extraction steps
    output.update(_extract_top_ratios(soup))
    output.update(_extract_text_data(soup))

    # Time-series and structured tables
    output["quarters"] = _extract_table(soup, "quarterly-results")
    output["profit_loss"] = _extract_table(soup, "profit-loss")
    output["balance_sheet"] = _extract_table(soup, "balance-sheet")
    output["cash_flow"] = _extract_table(soup, "cash-flow")

    # Flat blocks (Ratios/Growth)
    output["ratios"] = _extract_flat_metrics(soup, "ratios")
    output["growth"] = _extract_flat_metrics(soup, "compounded-sales-growth")

    # Shareholding (full time-series)
    output["shareholding"] = _extract_shareholding(soup)

    if not output.get(SCREENER_FIELDS["top_ratios"]["marketcap"]):
        log.warning(f"[FUNDAMENTALS] Missing core data (Market Cap) for {symbol}")

    return output


# ------------------------------------------------------------
# Save JSON / Public API (Snippets show this is standard)
# ------------------------------------------------------------
def save_processed(symbol: str, data: Dict[str, Any]) -> Path:
    p = PROCESSED_DIR / f"{symbol}.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p

# Utility function from snippet
def _sleep_with_jitter(t):
    time.sleep(t)

def scrape(symbol: str, *, save: bool = True) -> Dict[str, Any]:
    data = extract_fundamentals(symbol)
    if save and data:
        save_processed(symbol, data)
    return data

def scrape_many(symbols: List[str]) -> None:
    symbols = [s.upper().strip() for s in symbols if s.strip()]
    sym_sleep_min = float(S.get("SYMBOL_SLEEP_MIN", 1.6))
    sym_sleep_max = float(S.get("SYMBOL_SLEEP_MAX", 3.8))

    for i, sym in enumerate(symbols, start=1):
        try:
            log.info(f"[FUNDAMENTALS] ({i}/{len(symbols)}) Scraping {sym}")
            scrape(sym)
        except Exception as e:
            log.error(f"[FUNDAMENTALS] Error scraping {sym}: {e}")

        _sleep_with_jitter(
            random.uniform(sym_sleep_min, sym_sleep_max)
        )
