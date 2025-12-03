#!/usr/bin/env python3
"""
============================================================
queen/fetchers/fundamentals_scraper.py — v7.0 (COMPLETE EXTRACTION)
============================================================
Screener.in Fundamentals Scraper - Full Data Extraction

Features:
    - Multi-threaded parallel fetching (ThreadPoolExecutor)
    - Token bucket rate limiting
    - Automatic checkpointing and resume
    - Complete data extraction: Growth, Peers, Pledge, etc.
    - Integrated with queen.settings

Usage:
    python -m queen.fetchers.fundamentals_scraper --symbol TCS
    python -m queen.fetchers.fundamentals_scraper RELIANCE TCS INFY
    python -m queen.fetchers.fundamentals_scraper --batch universe.csv --workers 4
    python -m queen.fetchers.fundamentals_scraper --analyze data/fundamentals/raw/TCS.html

Requirements:
    pip install requests beautifulsoup4 lxml
============================================================
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

try:
    import requests
    from bs4 import BeautifulSoup as BS
except ImportError:
    print("ERROR: Missing required packages. Install with:")
    print("  pip install requests beautifulsoup4 lxml")
    sys.exit(1)


# ============================================================
# PROJECT INTEGRATION - Import from queen.settings
# ============================================================

_PROJECT_INTEGRATED = False
_SETTINGS_PATHS = None
_SETTINGS_FETCH = None
_FUNDAMENTALS_MAP = None

try:
    from queen.settings.settings import PATHS, FETCH, EXTERNAL_APIS
    from queen.settings.fundamentals_map import (
        SCREENER_FIELDS as PROJECT_SCREENER_FIELDS,
        FUNDAMENTALS_BASE_SCHEMA,
        FUNDAMENTALS_ADAPTER_COLUMNS,
        FUNDAMENTALS_METRIC_COLUMNS,
        GROWTH_FIELDS as PROJECT_GROWTH_FIELDS,
        PEER_FIELDS as PROJECT_PEER_FIELDS,
    )
    _PROJECT_INTEGRATED = True
    _SETTINGS_PATHS = PATHS
    _SETTINGS_FETCH = FETCH.get("FUNDAMENTALS", {})
    _FUNDAMENTALS_MAP = PROJECT_SCREENER_FIELDS
    print("[INFO] Loaded settings from queen.settings")
except ImportError as e:
    print(f"[INFO] Running standalone (queen.settings not found: {e})")
    _PROJECT_INTEGRATED = False


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """All configuration in one place. Uses project settings if available."""

    # Base URL for Screener.in
    BASE_URL = "https://www.screener.in"
    COMPANY_URL = "https://www.screener.in/company/"

    # Output directories
    if _PROJECT_INTEGRATED and _SETTINGS_PATHS:
        OUTPUT_DIR = _SETTINGS_PATHS.get("FUNDAMENTALS_OUTPUT", Path("data/fundamentals"))
        RAW_DIR = _SETTINGS_PATHS.get("FUNDAMENTALS_RAW", OUTPUT_DIR / "raw")
        PROCESSED_DIR = _SETTINGS_PATHS.get("FUNDAMENTALS_PROCESSED", OUTPUT_DIR / "processed")
    else:
        OUTPUT_DIR = Path("data/fundamentals")
        RAW_DIR = OUTPUT_DIR / "raw"
        PROCESSED_DIR = OUTPUT_DIR / "processed"

    # Request settings
    if _PROJECT_INTEGRATED and _SETTINGS_FETCH:
        REQUEST_TIMEOUT = _SETTINGS_FETCH.get("REQUEST_TIMEOUT", 30)
        MAX_RETRIES = _SETTINGS_FETCH.get("MAX_RETRIES", 3)
        RETRY_SLEEP_BASE = _SETTINGS_FETCH.get("RETRY_SLEEP_BASE", 2.0)
        SYMBOL_SLEEP_MIN = _SETTINGS_FETCH.get("SYMBOL_SLEEP_MIN", 2.0)
        SYMBOL_SLEEP_MAX = _SETTINGS_FETCH.get("SYMBOL_SLEEP_MAX", 4.0)
        MAX_WORKERS = _SETTINGS_FETCH.get("MAX_WORKERS", 3)
        USER_AGENTS = _SETTINGS_FETCH.get("USER_AGENTS", [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        ])
    else:
        REQUEST_TIMEOUT = 30
        MAX_RETRIES = 3
        RETRY_SLEEP_BASE = 2.0
        SYMBOL_SLEEP_MIN = 2.5
        SYMBOL_SLEEP_MAX = 5.0
        MAX_WORKERS = 3
        USER_AGENTS = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]

    # Rate limiting
    RATE_LIMIT_RPM = 20
    RATE_LIMIT_BURST = 3

    # Debug mode
    DEBUG = True

    # Batch processing
    BATCH_CHECKPOINT_INTERVAL = 10
    BATCH_PAUSE_ON_429 = 120

    # Project integration flag
    PROJECT_INTEGRATED = _PROJECT_INTEGRATED


# ============================================================
# FIELD MAPPINGS (Used if not imported from project)
# ============================================================

SCREENER_FIELDS = {
    "top_ratios": {
        "marketcap": "market_cap",
        "currentprice": "current_price",
        "stockpe": "pe_ratio",
        "pe": "pe_ratio",
        "bookvalue": "book_value",
        "dividendyield": "dividend_yield",
        "roce": "roce_pct",
        "roe": "roe_pct",
        "debttoequity": "debt_to_equity",
        "eps": "eps_ttm",
        "epsttm": "eps_ttm",
        "facevalue": "face_value",
        "highlow": "price_high_low",
        "grossnpa": "gross_npa_pct",
        "netnpa": "net_npa_pct",
        "casa": "casa_pct",
        "car": "car_pct",
        "capitaladequacyratio": "car_pct",
    },
    "ratios": {
        "debtordays": "ratio_debtor_days",
        "inventorydays": "ratio_inventory_days",
        "dayspayable": "ratio_days_payable",
        "cashconversioncycle": "ratio_cash_conversion_cycle",
        "workingcapitaldays": "ratio_working_capital_days",
        "roce": "ratio_roce_pct",
        "roe": "ratio_roe_pct",
        "interestcoverage": "interest_coverage",
        "interestcoverageratio": "interest_coverage",
    },
    "shareholding": {
        "promoters": "sh_promoters_pct",
        "promoter": "sh_promoters_pct",
        "fiis": "sh_fii_pct",
        "fii": "sh_fii_pct",
        "foreign": "sh_fii_pct",
        "diis": "sh_dii_pct",
        "dii": "sh_dii_pct",
        "public": "sh_public_pct",
        "government": "sh_govt_pct",
        "govt": "sh_govt_pct",
    },
}

GROWTH_FIELDS = {
    "compounded sales growth": {
        "10 years": "sales_cagr_10y",
        "5 years": "sales_cagr_5y",
        "3 years": "sales_cagr_3y",
        "ttm": "sales_cagr_ttm",
    },
    "compounded profit growth": {
        "10 years": "profit_cagr_10y",
        "5 years": "profit_cagr_5y",
        "3 years": "profit_cagr_3y",
        "ttm": "profit_cagr_ttm",
    },
    "stock price cagr": {
        "10 years": "price_cagr_10y",
        "5 years": "price_cagr_5y",
        "3 years": "price_cagr_3y",
        "1 year": "price_cagr_1y",
    },
    "return on equity": {
        "10 years": "roe_10y",
        "5 years": "roe_5y",
        "3 years": "roe_3y",
        "last year": "roe_last_year",
    },
    "return on capital employed": {
        "10 years": "roce_10y",
        "5 years": "roce_5y",
        "3 years": "roce_3y",
        "last year": "roce_last_year",
    },
}

PEER_FIELDS = {
    "name": "peer_name",
    "s.no.": "_skip",
    "cmp": "peer_cmp",
    "p/e": "peer_pe",
    "pe": "peer_pe",
    "mar cap": "peer_market_cap",
    "market cap": "peer_market_cap",
    "div yld": "peer_div_yield",
    "dividend yield": "peer_div_yield",
    "np qtr": "peer_np_qtr",
    "qtr profit": "peer_np_qtr",
    "qtr sales": "peer_sales_qtr",
    "sales qtr": "peer_sales_qtr",
    "roce": "peer_roce",
    "roce %": "peer_roce",
}


# ============================================================
# LOGGER (Thread-Safe)
# ============================================================

class Logger:
    """Thread-safe colored logger."""

    _lock = threading.Lock()

    COLORS = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "DEBUG": "\033[96m",
        "RESET": "\033[0m",
    }

    @classmethod
    def _log(cls, level: str, msg: str):
        with cls._lock:
            color = cls.COLORS.get(level, "")
            reset = cls.COLORS["RESET"]
            timestamp = datetime.now().strftime("%H:%M:%S")
            thread_name = threading.current_thread().name[:8]
            print(f"{color}[{timestamp}] [{level:7}] {msg}{reset}")

    @classmethod
    def info(cls, msg: str):
        cls._log("INFO", msg)

    @classmethod
    def success(cls, msg: str):
        cls._log("SUCCESS", msg)

    @classmethod
    def warning(cls, msg: str):
        cls._log("WARNING", msg)

    @classmethod
    def error(cls, msg: str):
        cls._log("ERROR", msg)

    @classmethod
    def debug(cls, msg: str):
        if Config.DEBUG:
            cls._log("DEBUG", msg)


log = Logger()


# ============================================================
# RATE LIMITER (Token Bucket)
# ============================================================

class RateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, requests_per_minute: float = 20, burst: int = 3):
        self.rate = requests_per_minute / 60.0
        self.capacity = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = threading.Lock()
        self._request_times: List[float] = []

    def acquire(self, timeout: float = 60.0) -> bool:
        start = time.time()

        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    self._request_times.append(now)
                    self._request_times = [t for t in self._request_times if now - t < 60]
                    return True

            if time.time() - start > timeout:
                return False

            time.sleep(0.5)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            recent = [t for t in self._request_times if now - t < 60]
            return {
                "tokens_available": self.tokens,
                "requests_last_minute": len(recent),
                "rate_per_minute": self.rate * 60,
            }


# ============================================================
# PROGRESS TRACKER
# ============================================================

@dataclass
class ScrapeStats:
    """Thread-safe scrape statistics."""
    total: int = 0
    completed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def increment(self, success: bool = True, skipped: bool = False):
        with self._lock:
            self.completed += 1
            if skipped:
                self.skipped += 1
            elif success:
                self.success += 1
            else:
                self.failed += 1

    def get_progress(self) -> str:
        with self._lock:
            elapsed = time.time() - self.start_time
            rate = self.completed / elapsed if elapsed > 0 else 0
            eta = (self.total - self.completed) / rate if rate > 0 else 0
            return (
                f"Progress: {self.completed}/{self.total} "
                f"(✓{self.success} ✗{self.failed} ⊘{self.skipped}) "
                f"| Rate: {rate:.1f}/s | ETA: {eta:.0f}s"
            )


# ============================================================
# SESSION MANAGER (Thread-Safe)
# ============================================================

class SessionManager:
    """Thread-safe HTTP session manager with rate limiting."""

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
        self._sessions: Dict[int, requests.Session] = {}
        self._lock = threading.Lock()
        self._warm = False

    def _get_session(self) -> requests.Session:
        thread_id = threading.get_ident()

        with self._lock:
            if thread_id not in self._sessions:
                session = requests.Session()
                session.headers.update({
                    "User-Agent": random.choice(Config.USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Cache-Control": "max-age=0",
                })
                self._sessions[thread_id] = session
            return self._sessions[thread_id]

    def warm_up(self):
        if self._warm:
            return True

        try:
            log.info("Warming up session...")
            session = self._get_session()
            resp = session.get(Config.BASE_URL, timeout=15)
            resp.raise_for_status()
            time.sleep(random.uniform(1.0, 2.0))
            self._warm = True
            log.success("Session ready")
            return True
        except Exception as e:
            log.warning(f"Warm-up failed: {e}")
            return False

    def get(self, url: str, retries: int = None) -> Optional[requests.Response]:
        retries = retries or Config.MAX_RETRIES
        session = self._get_session()

        for attempt in range(retries):
            if not self.rate_limiter.acquire(timeout=120):
                log.warning(f"Rate limiter timeout for {url}")
                return None

            try:
                if attempt > 0:
                    session.headers["User-Agent"] = random.choice(Config.USER_AGENTS)
                    time.sleep(Config.RETRY_SLEEP_BASE * (2 ** attempt))

                resp = session.get(url, timeout=Config.REQUEST_TIMEOUT)

                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 404:
                    log.error(f"Page not found (404): {url}")
                    return None
                elif resp.status_code == 429:
                    log.warning(f"Rate limited (429). Pausing {Config.BATCH_PAUSE_ON_429}s...")
                    time.sleep(Config.BATCH_PAUSE_ON_429)
                else:
                    log.warning(f"HTTP {resp.status_code} for {url}")

            except requests.exceptions.Timeout:
                log.warning(f"Timeout on attempt {attempt + 1}/{retries}")
            except requests.exceptions.RequestException as e:
                log.warning(f"Request error on attempt {attempt + 1}/{retries}: {e}")

        log.error(f"All {retries} attempts failed for {url}")
        return None


# ============================================================
# VALUE PARSERS
# ============================================================

def parse_number(value: str) -> Optional[float]:
    """Parse Indian number format to float."""
    if not value or not isinstance(value, str):
        return None

    text = value.strip()
    if not text or text == "-" or text.lower() in ("na", "n/a", ""):
        return None

    multiplier = 1.0
    text_lower = text.lower()
    if "cr" in text_lower:
        multiplier = 1  # Keep in crores
    elif "lakh" in text_lower or "lac" in text_lower:
        multiplier = 0.01  # Convert to crores

    # Remove all non-numeric except decimal and minus
    cleaned = re.sub(r'[^\d.\-]', '', text)

    # Handle multiple decimal points
    parts = cleaned.split('.')
    if len(parts) > 2:
        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]

    try:
        return float(cleaned) * multiplier
    except (ValueError, TypeError):
        return None


def parse_percentage(value: str) -> Optional[float]:
    """Parse percentage string to float."""
    if not value:
        return None
    # Remove % sign and parse
    cleaned = value.replace('%', '').strip()
    return parse_number(cleaned)


def normalize_key(key: str) -> str:
    """Normalize a key for matching."""
    return (key.lower().strip()
            .replace('%', '')
            .replace('/', '')
            .replace(' ', '')
            .replace('\n', '')
            .replace('\t', '')
            .replace('+', '')
            .replace('.', '')
            .replace('₹', '')
            .replace(',', ''))


# ============================================================
# DATA EXTRACTOR
# ============================================================

class DataExtractor:
    """Extract structured data from Screener.in HTML."""

    def __init__(self, soup: BS, symbol: str):
        self.soup = soup
        self.symbol = symbol
        self.data: Dict[str, Any] = {"symbol": symbol}

    def extract_all(self) -> Dict[str, Any]:
        """Run all extractors and return complete data."""
        # Metadata
        self._extract_metadata()

        # Top ratios
        self._extract_top_ratios()

        # Text data
        self._extract_about()
        self._extract_pros_cons()

        # Financial tables
        self.data["quarters"] = self._extract_financial_table("quarters")
        self.data["profit_loss"] = self._extract_financial_table("profit-loss")
        self.data["balance_sheet"] = self._extract_financial_table("balance-sheet")
        self.data["cash_flow"] = self._extract_financial_table("cash-flow")

        # Ratios
        self.data["ratios"] = self._extract_ratios_table()

        # Growth (from ranges-table elements)
        self.data["growth"] = self._extract_growth()

        # Shareholding (with pledge data)
        self.data["shareholding"] = self._extract_shareholding()

        # Peers comparison
        self.data["peers"] = self._extract_peers()

        # Post-processing
        self._post_process()
        self._flatten_for_adapter()

        self.data["_extracted_at"] = datetime.now().isoformat()

        return self.data

    def _extract_metadata(self):
        """Extract company name, sector, etc."""
        # Company name
        h1 = self.soup.find("h1")
        if h1:
            self.data["company_name"] = h1.get_text(strip=True)

        # Sector (from title="Sector" attribute)
        sector_link = self.soup.find("a", attrs={"title": "Sector"})
        if sector_link:
            self.data["sector"] = sector_link.get_text(strip=True)
            self.data["industry"] = sector_link.get_text(strip=True)

        # Broad sector
        broad_sector_link = self.soup.find("a", attrs={"title": "Broad Sector"})
        if broad_sector_link:
            self.data["broad_sector"] = broad_sector_link.get_text(strip=True)
            if not self.data.get("sector"):
                self.data["sector"] = broad_sector_link.get_text(strip=True)

        # Industry (more specific)
        industry_link = self.soup.find("a", attrs={"title": "Industry"})
        if industry_link:
            self.data["industry"] = industry_link.get_text(strip=True)

        # BSE/NSE codes
        company_info = self.soup.find("div", id="company-info")
        if company_info:
            text = company_info.get_text()

            # BSE code
            bse_match = re.search(r'BSE:\s*(\d+)', text)
            if bse_match:
                self.data["bse_code"] = bse_match.group(1)

            # NSE code
            nse_match = re.search(r'NSE:\s*(\w+)', text)
            if nse_match:
                self.data["nse_code"] = nse_match.group(1)

    def _extract_top_ratios(self):
        """Extract key ratios from the top section."""
        top_ratios_ul = self.soup.find("ul", id="top-ratios")
        if not top_ratios_ul:
            return

        for li in top_ratios_ul.find_all("li"):
            text = li.get_text(separator=" | ", strip=True)

            # High / Low special handling
            if "High" in text and "Low" in text:
                numbers = re.findall(r'[\d,]+(?:\.\d+)?', text)
                if len(numbers) >= 2:
                    self.data["week_52_high"] = parse_number(numbers[0])
                    self.data["week_52_low"] = parse_number(numbers[1])
                continue

            # Get label and value
            name_span = li.find("span", class_="name")
            if not name_span:
                continue

            label = name_span.get_text(strip=True)

            # Get the number span
            number_span = li.find("span", class_="number")
            if number_span:
                value = parse_number(number_span.get_text(strip=True))
            else:
                # Fallback: extract from full text
                li_text = li.get_text(strip=True)
                numbers = re.findall(r'[\d,]+(?:\.\d+)?', li_text)
                value = parse_number(numbers[-1]) if numbers else None

            if value is None:
                continue

            # Map to internal field
            norm_label = normalize_key(label)
            field_map = SCREENER_FIELDS.get("top_ratios", {})

            matched = False
            for key, internal_field in field_map.items():
                if normalize_key(key) == norm_label or key in norm_label:
                    self.data[internal_field] = value
                    matched = True
                    break

            if not matched:
                # Direct mapping for common fields
                if "market" in norm_label and "cap" in norm_label:
                    self.data["market_cap"] = value
                elif "current" in norm_label and "price" in norm_label:
                    self.data["current_price"] = value
                elif norm_label == "stockpe" or norm_label == "pe":
                    self.data["pe_ratio"] = value
                elif "book" in norm_label and "value" in norm_label:
                    self.data["book_value"] = value
                elif "dividend" in norm_label and "yield" in norm_label:
                    self.data["dividend_yield"] = value
                elif norm_label == "roce":
                    self.data["roce_pct"] = value
                elif norm_label == "roe":
                    self.data["roe_pct"] = value
                elif "face" in norm_label and "value" in norm_label:
                    self.data["face_value"] = value
                elif "eps" in norm_label:
                    self.data["eps_ttm"] = value
                elif "debt" in norm_label and "equity" in norm_label:
                    self.data["debt_to_equity"] = value

    def _extract_about(self):
        """Extract company description."""
        about_section = (
            self.soup.find("div", class_="about")
            or self.soup.find("div", id="about")
            or self.soup.find("section", id="about")
        )
        if about_section:
            p = about_section.find("p")
            if p:
                self.data["about"] = p.get_text(strip=True)

    def _extract_pros_cons(self):
        """Extract pros and cons lists."""
        # Look inside the analysis section
        analysis = self.soup.find("section", id="analysis")
        if analysis:
            pros_div = analysis.find("div", class_="pros")
            if pros_div:
                items = [li.get_text(strip=True) for li in pros_div.find_all("li")]
                if items:
                    self.data["pros"] = items

            cons_div = analysis.find("div", class_="cons")
            if cons_div:
                items = [li.get_text(strip=True) for li in cons_div.find_all("li")]
                if items:
                    self.data["cons"] = items

    def _extract_financial_table(self, section_id: str) -> Dict[str, Dict[str, Any]]:
        """Extract a financial table (quarters, P&L, BS, CF)."""
        result = {}
        section = self._find_section(section_id)
        if not section:
            return result

        table = section.find("table")
        if not table:
            return result

        # Get headers (periods)
        headers = []
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [th.get_text(strip=True) for th in first_row.find_all(["th", "td"])]

        period_headers = headers[1:] if headers else []

        # Get data rows
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            row_label = cells[0].get_text(strip=True)
            if not row_label or row_label in period_headers:
                continue

            row_data = {}
            for i, cell in enumerate(cells[1:]):
                if i < len(period_headers):
                    period = period_headers[i]
                    value_text = cell.get_text(strip=True)
                    parsed = parse_number(value_text)
                    row_data[period] = parsed if parsed is not None else value_text

            if row_data:
                result[row_label] = row_data

        return result

    def _extract_ratios_table(self) -> Dict[str, Any]:
        """Extract ratios section."""
        result = {}
        section = self._find_section("ratios")
        if not section:
            return result

        table = section.find("table")
        if not table:
            return result

        # Get headers
        headers = []
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

        period_headers = headers[1:] if headers else []

        # Get data
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            key = cells[0].get_text(strip=True)

            # Get latest value (last column with data)
            value = None
            for cell in reversed(cells[1:]):
                cell_text = cell.get_text(strip=True)
                if cell_text and cell_text != "-":
                    value = parse_number(cell_text)
                    break

            if value is not None:
                norm_key = normalize_key(key)
                field_map = SCREENER_FIELDS.get("ratios", {})

                for field_key, internal_key in field_map.items():
                    if normalize_key(field_key) == norm_key:
                        result[internal_key] = value
                        break

        return result

    def _extract_growth(self) -> Dict[str, Any]:
        """Extract growth metrics from ranges-table elements."""
        result = {}

        # The growth data is in <table class="ranges-table"> elements
        ranges_tables = self.soup.find_all("table", class_="ranges-table")

        if ranges_tables:
            log.debug(f"Found {len(ranges_tables)} ranges-table elements")

            for table in ranges_tables:
                # Get the category from the header (th with colspan)
                header_th = table.find("th")
                if not header_th:
                    continue

                category_text = header_th.get_text(strip=True).lower()

                # Map category to our GROWTH_FIELDS keys
                category = None
                for cat_key in GROWTH_FIELDS.keys():
                    if cat_key.lower() in category_text or category_text in cat_key.lower():
                        category = cat_key
                        break

                if not category:
                    # Try partial matching
                    if "sales" in category_text and "growth" in category_text:
                        category = "compounded sales growth"
                    elif "profit" in category_text and "growth" in category_text:
                        category = "compounded profit growth"
                    elif "price" in category_text or "stock" in category_text:
                        category = "stock price cagr"
                    elif "return on equity" in category_text or (category_text == "roe"):
                        category = "return on equity"
                    elif "return on capital" in category_text or (category_text == "roce"):
                        category = "return on capital employed"

                if not category:
                    log.debug(f"Unknown growth category: {category_text}")
                    continue

                # Parse rows
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        period_text = cells[0].get_text(strip=True).lower().replace(":", "").strip()
                        value_text = cells[1].get_text(strip=True)

                        parsed_value = parse_percentage(value_text)
                        if parsed_value is None:
                            continue

                        # Map period to internal key
                        if category in GROWTH_FIELDS:
                            for period_key, internal_key in GROWTH_FIELDS[category].items():
                                # Flexible matching
                                if period_key in period_text or period_text in period_key:
                                    result[internal_key] = parsed_value
                                    break
                                # Handle "10 years" vs "10 Years:" variations
                                period_normalized = period_text.replace(" ", "").replace("years", "y").replace("year", "y")
                                key_normalized = period_key.replace(" ", "").replace("years", "y").replace("year", "y")
                                if period_normalized == key_normalized:
                                    result[internal_key] = parsed_value
                                    break

        log.debug(f"Extracted growth metrics: {len(result)} fields")
        return result

    def _extract_shareholding(self) -> Dict[str, Any]:
        """Extract shareholding pattern with pledge data."""
        result = {
            "quarterly": {},
            "latest": {},
            "pledge": {}
        }

        section = self._find_section("shareholding")
        if not section:
            return result

        # Find main shareholding table
        table = section.find("table")
        if not table:
            return result

        # Get headers
        headers = []
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [th.get_text(strip=True) for th in first_row.find_all(["th", "td"])]

        period_headers = headers[1:] if headers else []

        # Category mapping
        category_map = {
            "promoter": "promoters",
            "promoters": "promoters",
            "fii": "fii",
            "fiis": "fii",
            "foreign": "fii",
            "dii": "dii",
            "diis": "dii",
            "domestic": "dii",
            "public": "public",
            "retail": "public",
            "govt": "government",
            "government": "government",
        }

        # Parse table
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            row_text = cells[0].get_text(strip=True).lower()

            # Determine category
            category = None
            for pattern, mapped in category_map.items():
                if pattern in row_text:
                    category = mapped
                    break

            if not category:
                continue

            # Extract time series
            series = {}
            for i, cell in enumerate(cells[1:]):
                if i < len(period_headers):
                    period = period_headers[i]
                    value = parse_percentage(cell.get_text(strip=True))
                    if value is not None:
                        series[period] = value

            if series:
                result["quarterly"][category] = series
                # Latest value (first period)
                if period_headers:
                    first_period = period_headers[0]
                    if first_period in series:
                        result["latest"][category] = series[first_period]

        # Extract pledge data
        self._extract_pledge_data(section, result)

        return result

    def _extract_pledge_data(self, section, result: Dict):
        """Extract promoter pledge data."""
        # Look for pledge information in the shareholding section
        section_text = section.get_text(separator=" ", strip=True).lower()

        # Pattern 1: "X% of promoter holding is pledged"
        pledge_patterns = [
            r'(\d+(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:promoter|promoters?)?\s*(?:holding|shares?)?\s*(?:is|are)?\s*pledged',
            r'pledged\s*[:\s]+(\d+(?:\.\d+)?)\s*%',
            r'pledge\s*[:\s]+(\d+(?:\.\d+)?)\s*%',
            r'promoter\s+pledge\s*[:\s]+(\d+(?:\.\d+)?)\s*%',
        ]

        for pattern in pledge_patterns:
            match = re.search(pattern, section_text)
            if match:
                pledge_pct = float(match.group(1))
                result["pledge"]["promoter_pledge_pct"] = pledge_pct
                self.data["promoter_pledge_pct"] = pledge_pct
                break

        # Also look for pledge table
        pledge_table = None
        for table in section.find_all("table"):
            table_text = table.get_text(strip=True).lower()
            if "pledge" in table_text:
                pledge_table = table
                break

        if pledge_table:
            rows = pledge_table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    if "pledge" in label:
                        value = parse_percentage(cells[-1].get_text(strip=True))
                        if value is not None:
                            result["pledge"]["promoter_pledge_pct"] = value
                            self.data["promoter_pledge_pct"] = value

    def _extract_peers(self) -> List[Dict[str, Any]]:
        """Extract peer comparison table."""
        result = []

        section = self._find_section("peers")
        if not section:
            log.debug("Peers section not found")
            return result

        # Find all tables in peers section - the data table has class "data-table"
        tables = section.find_all("table", class_="data-table")
        if not tables:
            # Try finding any table
            tables = section.find_all("table")

        if not tables:
            log.debug("No table in peers section")
            return result

        for table in tables:
            # Get headers
            headers = []
            thead = table.find("thead")
            if thead:
                header_row = thead.find("tr")
                if header_row:
                    headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

            if not headers:
                first_row = table.find("tr")
                if first_row:
                    headers = [th.get_text(strip=True).lower() for th in first_row.find_all(["th", "td"])]

            # Skip if doesn't look like a peer table
            if not any(h in headers for h in ["name", "s.no.", "cmp", "p/e", "market cap", "mar cap"]):
                continue

            # Map headers to internal fields
            header_mapping = []
            for h in headers:
                norm_h = normalize_key(h)
                mapped = None
                for field_key, internal_key in PEER_FIELDS.items():
                    if normalize_key(field_key) == norm_h or field_key in h:
                        mapped = internal_key
                        break
                header_mapping.append(mapped)

            # Parse rows
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells or len(cells) < 2:
                    continue

                peer_data = {}

                for i, cell in enumerate(cells):
                    if i >= len(header_mapping):
                        break

                    field = header_mapping[i]
                    if not field or field == "_skip":
                        continue

                    value = cell.get_text(strip=True)

                    # First column is usually name with link
                    if i == 0 or field == "peer_name":
                        link = cell.find("a")
                        if link:
                            peer_data["name"] = link.get_text(strip=True)
                            href = link.get("href", "")
                            if "/company/" in href:
                                peer_data["symbol"] = href.split("/company/")[-1].rstrip("/").upper()
                        else:
                            peer_data["name"] = value
                    else:
                        parsed = parse_number(value)
                        peer_data[field] = parsed if parsed is not None else value

                if peer_data.get("name"):
                    result.append(peer_data)

        log.debug(f"Extracted {len(result)} peers")
        return result

    def _post_process(self):
        """Fill in missing fields from alternative sources."""
        # EPS from P&L if missing
        if not self.data.get("eps_ttm") and self.data.get("profit_loss"):
            pl = self.data["profit_loss"]
            eps_row = pl.get("EPS in Rs") or pl.get("EPS")
            if eps_row and isinstance(eps_row, dict):
                ttm_val = eps_row.get("TTM")
                if ttm_val is not None:
                    self.data["eps_ttm"] = ttm_val

        # Debt to Equity from Balance Sheet
        if not self.data.get("debt_to_equity") and self.data.get("balance_sheet"):
            bs = self.data["balance_sheet"]
            borrowings_row = bs.get("Borrowings+") or bs.get("Borrowings")
            reserves_row = bs.get("Reserves")
            equity_row = bs.get("Equity Capital")

            if borrowings_row and reserves_row and equity_row:
                # Get latest period values
                for row in [borrowings_row, reserves_row, equity_row]:
                    if isinstance(row, dict):
                        periods = list(row.keys())
                        if periods:
                            latest = periods[-1]  # Usually latest is last
                            borrowings = borrowings_row.get(latest) if isinstance(borrowings_row, dict) else None
                            reserves = reserves_row.get(latest) if isinstance(reserves_row, dict) else None
                            equity = equity_row.get(latest) if isinstance(equity_row, dict) else None

                            if all(v is not None for v in [borrowings, reserves, equity]):
                                try:
                                    total_equity = float(equity) + float(reserves)
                                    if total_equity > 0:
                                        self.data["debt_to_equity"] = round(float(borrowings) / total_equity, 2)
                                except (ValueError, TypeError):
                                    pass
                            break

    def _flatten_for_adapter(self):
        """Flatten nested data for easier consumption."""
        # Flatten shareholding latest
        shareholding = self.data.get("shareholding", {})
        latest_sh = shareholding.get("latest", {})
        if latest_sh:
            self.data["sh_promoters_pct"] = latest_sh.get("promoters")
            self.data["sh_fii_pct"] = latest_sh.get("fii")
            self.data["sh_dii_pct"] = latest_sh.get("dii")
            self.data["sh_public_pct"] = latest_sh.get("public")
            self.data["sh_govt_pct"] = latest_sh.get("government")

        # Flatten growth
        growth = self.data.get("growth", {})
        for key, value in growth.items():
            if value is not None and key not in self.data:
                self.data[key] = value

        # Flatten ratios
        ratios = self.data.get("ratios", {})
        for key, value in ratios.items():
            if value is not None and key not in self.data:
                self.data[key] = value

        # Latest quarterly values
        quarters = self.data.get("quarters", {})
        if quarters:
            for row_name, row_data in quarters.items():
                if isinstance(row_data, dict) and row_data:
                    periods = list(row_data.keys())
                    if periods:
                        latest_period = periods[-1]
                        latest_value = row_data.get(latest_period)

                        if "Sales" in row_name:
                            self.data["q_sales_latest"] = latest_value
                        elif "Net Profit" in row_name:
                            self.data["q_net_profit_latest"] = latest_value
                        elif "EPS" in row_name:
                            self.data["q_eps_latest"] = latest_value

        # TTM values from P&L
        pl = self.data.get("profit_loss", {})
        if pl:
            for row_name, row_data in pl.items():
                if isinstance(row_data, dict):
                    ttm_value = row_data.get("TTM")
                    if ttm_value is not None:
                        if "Sales" in row_name:
                            self.data["pl_sales_ttm"] = ttm_value
                        elif "Net Profit" in row_name:
                            self.data["pl_net_profit_ttm"] = ttm_value

    def _find_section(self, section_id: str) -> Optional[Any]:
        """Find a section by ID."""
        for id_variant in [section_id, section_id.replace("-", ""), section_id.replace("-", "_")]:
            section = (
                self.soup.find("section", id=id_variant) or
                self.soup.find("div", id=id_variant)
            )
            if section:
                return section
        return None


# ============================================================
# CHECKPOINT MANAGER
# ============================================================

class CheckpointManager:
    """Thread-safe checkpoint management."""

    def __init__(self, checkpoint_file: Path):
        self.checkpoint_file = checkpoint_file
        self._lock = threading.Lock()
        self._completed: Set[str] = set()
        self._results: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.checkpoint_file.exists():
            try:
                data = json.loads(self.checkpoint_file.read_text())
                self._completed = set(data.get("completed", []))
                self._results = data.get("results", {})
                log.info(f"Loaded checkpoint: {len(self._completed)} symbols done")
            except Exception as e:
                log.warning(f"Could not load checkpoint: {e}")

    def is_completed(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._completed

    def mark_completed(self, symbol: str, result: Dict[str, Any]):
        with self._lock:
            self._completed.add(symbol)
            self._results[symbol] = result

    def save(self):
        with self._lock:
            data = {
                "completed": list(self._completed),
                "results": self._results,
                "timestamp": datetime.now().isoformat(),
                "count": len(self._completed),
            }
            self.checkpoint_file.write_text(json.dumps(data, indent=2, default=str))

    def get_results(self) -> Dict[str, Any]:
        with self._lock:
            return self._results.copy()

    def get_completed(self) -> Set[str]:
        with self._lock:
            return self._completed.copy()


# ============================================================
# THREADED SCRAPER
# ============================================================

class ThreadedFundamentalsScraper:
    """Multi-threaded scraper with rate limiting and checkpointing."""

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or Config.MAX_WORKERS
        self.rate_limiter = RateLimiter(
            requests_per_minute=Config.RATE_LIMIT_RPM,
            burst=Config.RATE_LIMIT_BURST
        )
        self.session_mgr = SessionManager(self.rate_limiter)
        self._ensure_directories()

    def _ensure_directories(self):
        Config.RAW_DIR.mkdir(parents=True, exist_ok=True)
        Config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    def scrape_symbol(self, symbol: str, save: bool = True) -> Dict[str, Any]:
        """Scrape fundamentals for a single symbol."""
        symbol = symbol.upper().strip()
        url = f"{Config.COMPANY_URL}{symbol}/"

        log.info(f"Scraping {symbol}...")

        response = self.session_mgr.get(url)
        if not response:
            log.error(f"Failed to fetch {symbol}")
            return {"symbol": symbol, "_error": "Failed to fetch page"}

        # Save raw HTML
        if Config.DEBUG:
            raw_path = Config.RAW_DIR / f"{symbol}.html"
            raw_path.write_text(response.text, encoding="utf-8")
            log.debug(f"Saved raw HTML to {raw_path}")

        soup = BS(response.content, "lxml")
        extractor = DataExtractor(soup, symbol)
        data = extractor.extract_all()

        if save:
            json_path = Config.PROCESSED_DIR / f"{symbol}.json"
            json_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8"
            )
            log.success(f"Saved {symbol} to {json_path.name}")

        return data

    def _worker_scrape(
        self,
        symbol: str,
        checkpoint: CheckpointManager,
        stats: ScrapeStats,
        save: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """Worker function for thread pool."""

        if checkpoint.is_completed(symbol):
            stats.increment(success=True, skipped=True)
            log.debug(f"Skipping {symbol} (already done)")
            return symbol, checkpoint.get_results().get(symbol, {})

        # Random jitter
        time.sleep(random.uniform(Config.SYMBOL_SLEEP_MIN, Config.SYMBOL_SLEEP_MAX))

        try:
            result = self.scrape_symbol(symbol, save=save)
            success = bool(result.get("market_cap") or result.get("company_name"))

            if not result.get("_error"):
                checkpoint.mark_completed(symbol, result)

            stats.increment(success=success)
            return symbol, result

        except Exception as e:
            log.error(f"{symbol}: Error - {e}")
            stats.increment(success=False)
            return symbol, {"symbol": symbol, "_error": str(e)}

    def scrape_parallel(
        self,
        symbols: List[str],
        save: bool = True,
        checkpoint_file: Path = None
    ) -> Dict[str, Dict[str, Any]]:
        """Scrape multiple symbols in parallel."""
        symbols = [s.upper().strip() for s in symbols if s.strip()]
        checkpoint_file = checkpoint_file or Config.PROCESSED_DIR / "_checkpoint.json"

        checkpoint = CheckpointManager(checkpoint_file)
        stats = ScrapeStats(total=len(symbols))

        remaining = [s for s in symbols if not checkpoint.is_completed(s)]
        already_done = len(symbols) - len(remaining)

        if already_done > 0:
            stats.completed = already_done
            stats.success = already_done
            stats.skipped = already_done

        log.info(f"Parallel scrape: {len(remaining)} remaining of {len(symbols)} total")
        log.info(f"Workers: {self.max_workers}, Rate limit: {Config.RATE_LIMIT_RPM} req/min")

        if not remaining:
            log.success("All symbols already processed!")
            return checkpoint.get_results()

        self.session_mgr.warm_up()

        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="Scraper") as executor:
            future_to_symbol = {
                executor.submit(
                    self._worker_scrape, symbol, checkpoint, stats, save
                ): symbol
                for symbol in remaining
            }

            completed_since_checkpoint = 0

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]

                try:
                    sym, data = future.result()
                    results[sym] = data
                except Exception as e:
                    log.error(f"{symbol}: Unexpected error - {e}")
                    results[symbol] = {"symbol": symbol, "_error": str(e)}

                completed_since_checkpoint += 1

                if completed_since_checkpoint >= Config.BATCH_CHECKPOINT_INTERVAL:
                    checkpoint.save()
                    log.info(f"Checkpoint saved. {stats.get_progress()}")
                    completed_since_checkpoint = 0

                if stats.completed % 10 == 0:
                    log.info(stats.get_progress())

        checkpoint.save()

        all_results = checkpoint.get_results()
        all_results.update(results)

        combined_path = Config.PROCESSED_DIR / "_all_symbols.json"
        combined_path.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8"
        )

        log.success(f"\n{'='*60}")
        log.success(f"Scraping complete!")
        log.success(f"  Total: {stats.total}")
        log.success(f"  Success: {stats.success}")
        log.success(f"  Failed: {stats.failed}")
        log.success(f"  Skipped: {stats.skipped}")
        log.success(f"  Time: {time.time() - stats.start_time:.1f}s")
        log.success(f"  Output: {combined_path}")
        log.success(f"{'='*60}\n")

        return all_results

    def scrape_sequential(
        self,
        symbols: List[str],
        save: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """Scrape symbols sequentially."""
        symbols = [s.upper().strip() for s in symbols if s.strip()]
        results = {}

        log.info(f"Sequential scrape: {len(symbols)} symbols")

        self.session_mgr.warm_up()

        for i, symbol in enumerate(symbols, 1):
            log.info(f"[{i}/{len(symbols)}] {symbol}")

            try:
                data = self.scrape_symbol(symbol, save=save)
                results[symbol] = data
            except Exception as e:
                log.error(f"{symbol}: Error - {e}")
                results[symbol] = {"symbol": symbol, "_error": str(e)}

            if i < len(symbols):
                time.sleep(random.uniform(Config.SYMBOL_SLEEP_MIN, Config.SYMBOL_SLEEP_MAX))

        if save and results:
            combined_path = Config.PROCESSED_DIR / "_all_symbols.json"
            combined_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8"
            )
            log.success(f"Saved combined to {combined_path}")

        return results

    def print_summary(self, data: Dict[str, Any]):
        """Print a detailed summary of extracted data."""
        symbol = data.get("symbol", "?")

        print(f"\n{'='*70}")
        print(f"  📊 Summary for {symbol}")
        print('='*70)

        # Key metrics
        print("\n  💰 KEY METRICS:")
        key_fields = [
            ("Company", "company_name"),
            ("Sector", "sector"),
            ("Industry", "industry"),
            ("Market Cap (Cr)", "market_cap"),
            ("Current Price", "current_price"),
            ("P/E Ratio", "pe_ratio"),
            ("Book Value", "book_value"),
            ("ROCE %", "roce_pct"),
            ("ROE %", "roe_pct"),
            ("Debt/Equity", "debt_to_equity"),
            ("EPS (TTM)", "eps_ttm"),
            ("Dividend Yield %", "dividend_yield"),
            ("Face Value", "face_value"),
            ("52W High", "week_52_high"),
            ("52W Low", "week_52_low"),
        ]

        for label, key in key_fields:
            value = data.get(key)
            if value is None:
                display = "-"
            elif isinstance(value, float):
                display = f"{value:,.2f}"
            else:
                display = str(value)
            print(f"    {label:20}: {display}")

        # Shareholding
        print("\n  👥 SHAREHOLDING (Latest):")
        sh_fields = [
            ("Promoters", "sh_promoters_pct"),
            ("FII", "sh_fii_pct"),
            ("DII", "sh_dii_pct"),
            ("Public", "sh_public_pct"),
            ("Government", "sh_govt_pct"),
            ("Promoter Pledge", "promoter_pledge_pct"),
        ]

        for label, key in sh_fields:
            value = data.get(key)
            if value is not None:
                print(f"    {label:20}: {value:.2f}%")

        # Growth
        print("\n  📈 GROWTH (CAGR):")
        growth_fields = [
            ("Sales 10Y", "sales_cagr_10y"),
            ("Sales 5Y", "sales_cagr_5y"),
            ("Sales 3Y", "sales_cagr_3y"),
            ("Profit 10Y", "profit_cagr_10y"),
            ("Profit 5Y", "profit_cagr_5y"),
            ("Profit 3Y", "profit_cagr_3y"),
            ("Price 10Y", "price_cagr_10y"),
            ("Price 5Y", "price_cagr_5y"),
            ("Price 3Y", "price_cagr_3y"),
        ]

        has_growth = False
        for label, key in growth_fields:
            value = data.get(key)
            if value is not None:
                print(f"    {label:20}: {value:.1f}%")
                has_growth = True

        if not has_growth:
            print("    (No growth data extracted)")

        # Peers
        peers = data.get("peers", [])
        if peers:
            print(f"\n  🏢 PEERS ({len(peers)} companies):")
            for i, peer in enumerate(peers[:5]):  # Show top 5
                name = peer.get("name", "?")
                pe = peer.get("peer_pe", "-")
                mcap = peer.get("peer_market_cap", "-")
                print(f"    {i+1}. {name[:25]:25} P/E: {pe:>8}  MCap: {mcap}")
            if len(peers) > 5:
                print(f"    ... and {len(peers) - 5} more")
        else:
            print("\n  🏢 PEERS: (No peers extracted)")

        # Sections available
        sections = []
        for sec in ["quarters", "profit_loss", "balance_sheet", "cash_flow", "ratios", "growth", "shareholding", "peers"]:
            if data.get(sec):
                sections.append(sec)
        print(f"\n  📁 Sections: {', '.join(sections)}")

        print('='*70 + "\n")


# ============================================================
# CLI HELPERS
# ============================================================

def load_symbols_from_csv(file_path: str, symbol_column: str = None) -> List[str]:
    """Load symbols from a CSV file."""
    symbols = []
    path = Path(file_path)

    if not path.exists():
        log.error(f"File not found: {file_path}")
        return symbols

    with open(path, 'r') as f:
        reader = csv.DictReader(f)

        if not symbol_column:
            headers = reader.fieldnames or []
            for possible in ["symbol", "Symbol", "SYMBOL", "ticker", "Ticker", "scrip", "Scrip", "SCRIP"]:
                if possible in headers:
                    symbol_column = possible
                    break
            if not symbol_column and headers:
                symbol_column = headers[0]

        for row in reader:
            sym = row.get(symbol_column, "").strip()
            if sym and not sym.startswith("#"):
                symbols.append(sym.upper())

    log.info(f"Loaded {len(symbols)} symbols from {file_path}")
    return symbols


def load_symbols_from_file(file_path: str) -> List[str]:
    """Load symbols from a text file."""
    symbols = []
    path = Path(file_path)

    if not path.exists():
        log.error(f"File not found: {file_path}")
        return symbols

    with open(path, 'r') as f:
        for line in f:
            sym = line.strip()
            if sym and not sym.startswith("#"):
                symbols.append(sym.upper())

    log.info(f"Loaded {len(symbols)} symbols from {file_path}")
    return symbols


def debug_html_structure(html_path: str):
    """Analyze HTML structure for debugging."""
    html_file = Path(html_path)
    if not html_file.exists():
        print(f"File not found: {html_path}")
        return

    soup = BS(html_file.read_text(encoding="utf-8"), "lxml")

    print("\n" + "="*70)
    print("HTML STRUCTURE ANALYSIS")
    print("="*70)

    # Sections
    print("\n📦 SECTIONS:")
    for section in soup.find_all("section"):
        print(f"  - section#{section.get('id', 'NO-ID')}")

    # Top ratios
    print("\n📊 TOP RATIOS:")
    top_ratios = soup.find("ul", id="top-ratios")
    if top_ratios:
        for li in top_ratios.find_all("li")[:10]:
            text = li.get_text(separator=" | ", strip=True)[:60]
            print(f"  - {text}")

    # Company info
    print("\n🏢 COMPANY INFO:")
    h1 = soup.find("h1")
    if h1:
        print(f"  Name: {h1.get_text(strip=True)}")

    sector = soup.find("a", attrs={"title": "Sector"})
    if sector:
        print(f"  Sector: {sector.get_text(strip=True)}")

    broad_sector = soup.find("a", attrs={"title": "Broad Sector"})
    if broad_sector:
        print(f"  Broad Sector: {broad_sector.get_text(strip=True)}")

    # Growth data (ranges-table)
    print("\n📈 GROWTH DATA (ranges-table):")
    ranges_tables = soup.find_all("table", class_="ranges-table")
    if ranges_tables:
        print(f"  Found {len(ranges_tables)} ranges-table elements")
        for i, table in enumerate(ranges_tables):
            header = table.find("th")
            category = header.get_text(strip=True) if header else "Unknown"
            print(f"\n  📊 {category}:")
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    period = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    print(f"    - {period} {value}")
    else:
        print("  No ranges-table elements found")

    # Peers section
    print("\n🏢 PEERS SECTION:")
    peers = soup.find("section", id="peers")
    if peers:
        tables = peers.find_all("table", class_="data-table")
        print(f"  Found {len(tables)} data-table elements")

        for table in tables:
            thead = table.find("thead")
            if thead:
                headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]
                print(f"  Headers: {headers[:7]}")

            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            print(f"  Found {len(rows)} peer rows")

            for row in rows[:3]:
                cells = row.find_all("td")
                if cells:
                    name_cell = cells[0]
                    link = name_cell.find("a")
                    name = link.get_text(strip=True) if link else name_cell.get_text(strip=True)
                    print(f"    - {name[:30]}")
    else:
        print("  Peers section not found")

    # Shareholding section (for pledge)
    print("\n👥 SHAREHOLDING SECTION:")
    shareholding = soup.find("section", id="shareholding")
    if shareholding:
        text = shareholding.get_text(separator=" ", strip=True).lower()
        if "pledge" in text:
            print("  ✅ Contains pledge information")
            # Find pledge mention
            import re
            pledge_match = re.search(r'(\d+(?:\.\d+)?)\s*%[^%]*pledge', text)
            if pledge_match:
                print(f"  Pledge: {pledge_match.group(1)}%")
        else:
            print("  ❌ No pledge information found")

    print("\n" + "="*70)


# ============================================================
# MAIN CLI
# ============================================================

def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description="Screener.in Fundamentals Scraper v7.0 (Complete Extraction)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Single symbol
    python fundamentals_scraper.py --symbol TCS

    # Multiple symbols (sequential for <5)
    python fundamentals_scraper.py RELIANCE TCS INFY

    # Parallel scraping
    python fundamentals_scraper.py --parallel RELIANCE TCS INFY HDFCBANK

    # Batch from CSV
    python fundamentals_scraper.py --batch universe.csv --workers 4

    # Analyze HTML structure
    python fundamentals_scraper.py --analyze data/fundamentals/raw/TCS.html
        """
    )

    parser.add_argument("symbols", nargs="*", help="Stock symbols")
    parser.add_argument("-s", "--symbol", type=str, help="Single symbol")
    parser.add_argument("-f", "--file", type=str, help="Text file with symbols")
    parser.add_argument("--batch", type=str, metavar="CSV", help="CSV file for batch")
    parser.add_argument("--symbol-column", type=str, help="Column name in CSV")
    parser.add_argument("--parallel", nargs="*", metavar="SYMBOL", help="Parallel scrape")
    parser.add_argument("-w", "--workers", type=int, default=Config.MAX_WORKERS, help="Workers")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    parser.add_argument("--output-dir", type=str, help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--analyze", type=str, metavar="HTML", help="Analyze HTML")
    parser.add_argument("--rate-limit", type=int, default=Config.RATE_LIMIT_RPM, help="Req/min")

    args = parser.parse_args()

    # Analyze mode
    if args.analyze:
        debug_html_structure(args.analyze)
        return 0

    # Configure
    if args.output_dir:
        Config.OUTPUT_DIR = Path(args.output_dir)
        Config.RAW_DIR = Config.OUTPUT_DIR / "raw"
        Config.PROCESSED_DIR = Config.OUTPUT_DIR / "processed"

    if args.debug:
        Config.DEBUG = True

    if args.rate_limit:
        Config.RATE_LIMIT_RPM = args.rate_limit

    # Collect symbols
    symbols = []

    if args.symbol:
        symbols.append(args.symbol)

    if args.symbols:
        symbols.extend(args.symbols)

    if args.parallel:
        symbols.extend(args.parallel)

    if args.file:
        symbols.extend(load_symbols_from_file(args.file))

    if args.batch:
        symbols = load_symbols_from_csv(args.batch, args.symbol_column)

    # Default test
    if not symbols:
        symbols = ["RELIANCE", "TCS", "HDFCBANK"]
        log.info(f"No symbols provided. Using: {symbols}")

    # Initialize scraper
    scraper = ThreadedFundamentalsScraper(max_workers=args.workers)
    save = not args.no_save

    # Determine mode
    use_parallel = (
        args.parallel is not None or
        args.batch is not None or
        len(symbols) > 5
    )

    if use_parallel:
        log.info(f"PARALLEL mode: {args.workers} workers")
        results = scraper.scrape_parallel(symbols, save=save)
    elif len(symbols) == 1:
        data = scraper.scrape_symbol(symbols[0], save=save)
        scraper.print_summary(data)
        results = {symbols[0]: data}
    else:
        log.info("SEQUENTIAL mode")
        results = scraper.scrape_sequential(symbols, save=save)
        for sym, data in results.items():
            scraper.print_summary(data)

    # Check success
    success_count = sum(
        1 for d in results.values()
        if d.get("market_cap") or d.get("company_name")
    )

    if success_count > 0:
        log.success(f"Completed: {success_count}/{len(results)} successful")
        return 0
    else:
        log.warning("Completed with issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
