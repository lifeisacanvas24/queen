import time
import json
import random
import logging
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import requests
import polars as pl
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- Configuration ---
OUTPUT_FILE_CSV = "fundamental_data.csv"
OUTPUT_FILE_JSON = "fundamental_data.json"
OUTPUT_FILE_PARQUET = "fundamental_data.parquet"
MAX_WORKERS = 3
USER_AGENT_LIST = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Helper: Clean Numbers ---
def clean_number(value: Any) -> Optional[float]:
    """Robustly cleans string values into floats and handles 'Cr' suffix."""
    if not value: return None
    if isinstance(value, (int, float)): return float(value)

    s = str(value).replace(',', '').replace('₹', '').strip()

    multiplier = 1.0
    if s.lower().endswith('cr'):
        # Market Cap is usually in Crores, but other ratios might also have 'Cr'
        s = s[:-2].strip()
    elif s.lower().endswith('lakh'):
        multiplier = 0.01
        s = s[:-4].strip()

    if s in ['-', '', 'NaN', 'N/A', 'Not Available', '...', '...%']: return None

    try:
        # Final attempt to clean and convert
        if s.endswith('%'):
            s = s[:-1].strip()
            return float(s) / 100.0 * multiplier

        return float(s) * multiplier
    except ValueError:
        return None

# --- Browser Manager (Unchanged for stability) ---
class RobustBrowserManager:
    """Manages a headless Chrome instance with anti-detection flags."""
    def __init__(self):
        self.driver = None
        self.setup_browser()

    def setup_browser(self):
        try:
            opts = Options()
            opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument(f"--user-agent={random.choice(USER_AGENT_LIST)}")
            opts.add_argument("--window-size=1920,1080")

            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option('useAutomationExtension', False)

            prefs = {"profile.managed_default_content_settings.images": 2}
            opts.add_experimental_option("prefs", prefs)

            self.driver = webdriver.Chrome(options=opts)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        except Exception as e:
            logger.error(f"Browser setup failed: {e}")
            raise

    def get_page(self, url, timeout=20):
        try:
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(url)
            time.sleep(random.uniform(2.0, 4.0))
            return True
        except Exception as e:
            logger.warning(f"Failed to load {url}: {e}")
            return False

    def quit(self):
        if self.driver:
            self.driver.quit()

# --- Data Fetchers (NSE) ---
def fetch_nse_quote(symbol: str, session: requests.Session) -> Dict:
    """Fetches NSE live quote for cross-verification."""
    try:
        if not session.cookies:
            session.get("https://www.nseindia.com", headers={"User-Agent": USER_AGENT_LIST[0]}, timeout=10)

        url = f"https://www.nseindia.com/api/quote-equity?symbol={quote(symbol)}"
        resp = session.get(url, headers={"User-Agent": USER_AGENT_LIST[0]}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"NSE fetch failed for {symbol}: {e}")
        pass
    return {}

# --- CRITICAL FIX: Enhanced Screener Scraper ---
def scrape_screener(driver_manager: RobustBrowserManager, symbol: str) -> Dict:
    """
    Scrapes detailed fundamentals from Screener.in with improved resilience.
    Uses broader selectors and regex to catch missing data.
    """
    data = {}
    try:
        url = f"https://www.screener.in/company/{symbol}/"
        if not driver_manager.get_page(url):
            return data

        soup = BeautifulSoup(driver_manager.driver.page_source, 'html.parser')

        # 1. Primary Scrape: Top Ratios (ul#top-ratios)
        ratios_ul = soup.select_one("ul#top-ratios")
        if ratios_ul:
            for li in ratios_ul.find_all("li"):
                name_span = li.select_one("span.name")
                val_span = li.select_one("span.number")

                if name_span and val_span:
                    key = name_span.text.strip()
                    val = val_span.text.strip()

                    if "Market Cap" in key:
                        data["Market Cap"] = clean_number(val)
                    elif "Current Price" in key:
                        data["Current Price"] = clean_number(val)
                    elif "Stock P/E" in key or "P/E" in key:
                        data["Stock P/E"] = clean_number(val)
                    elif "ROCE" in key:
                        data["ROCE"] = clean_number(val)
                    elif "ROE" in key:
                        data["ROE"] = clean_number(val)
                    elif "PEG Ratio" in key:
                        data["PEG Ratio"] = clean_number(val)
                    elif "High / Low" in key:
                        parts = val.split("/")
                        if len(parts) == 2:
                            data["High"] = clean_number(parts[0])
                            data["Low"] = clean_number(parts[1])

        # 2. Secondary Scrape: Fallback for key missing data (Market Cap, ROCE, ROE, PEG)

        # Mapping key required metrics to labels used in the HTML
        KEY_MAPPING = {
            "Stock P/E": ["P/E", "Stock P/E"],
            "Market Cap": ["Market Cap", "M. Cap"],
            "ROCE": ["ROCE", "Return on Capital Employed"],
            "ROE": ["ROE", "Return on Equity"],
            "PEG Ratio": ["PEG Ratio"]
        }

        main_content = soup.select_one("div.company-page-header") # Search restricted to header area

        for key, labels in KEY_MAPPING.items():
            # Only try to find if data is currently missing
            if key not in data or data[key] is None:
                for label in labels:
                    # FIX: Changed 'text=' to 'string=' to remove DeprecationWarning
                    label_tag = main_content.find('span', class_='name', string=re.compile(r'^\s*' + re.escape(label) + r'\s*$', re.IGNORECASE))

                    if label_tag:
                        value_tag = label_tag.find_next_sibling('span', class_='number')

                        # Added more aggressive fallback to check parent/sibling structure
                        if not value_tag:
                            # Try finding the number span inside the parent element
                            value_tag = label_tag.parent.find('span', class_='number')

                        if value_tag:
                            data[key] = clean_number(value_tag.text.strip())
                            break # Found for this key

        # 3. Dedicated Market Cap Fallback (Critical for large/stable stocks)
        if data.get("Market Cap") is None:
            # Look for the market cap text in the general text of the header, which can be less structured
            market_cap_text_search = re.search(r'(Market Cap|M\. Cap|Mkt\. Cap)\s*₹\s*([\d,\.]+\s*Cr)', soup.text, re.IGNORECASE)
            if market_cap_text_search:
                data["Market Cap"] = clean_number(market_cap_text_search.group(2))

    except Exception as e:
        logger.debug(f"Screener scrape failed for {symbol}: {e}")

    # Ensure all required keys are present, even if None
    for required_key in ["Market Cap", "Stock P/E", "PEG Ratio", "ROCE", "ROE", "High", "Low", "Current Price"]:
        if required_key not in data:
            data[required_key] = None

    return data

# --- Worker Function (Aggregation) ---

def process_symbol(symbol_data: Dict) -> Dict:
    """Worker that fetches data for a single symbol object."""
    symbol = symbol_data.get("symbol")
    if not symbol: return {}

    session = requests.Session()
    browser = None

    try:
        logger.info(f"Processing {symbol}...")

        # 1. Scrape Screener (Primary source for fundamentals)
        browser = RobustBrowserManager()
        screener_data = scrape_screener(browser, symbol)

        # 2. Fetch NSE Data (Primary source for live price/high-low fallback)
        nse_data = fetch_nse_quote(symbol, session)

        # 3. Aggregate Data
        final_record = {
            "Symbol": symbol,
            "Sector": symbol_data.get("sector", "Unknown"),
            # Price: Prefer Screener, Fallback to NSE
            "Current Price": screener_data.get("Current Price") or nse_data.get("priceInfo", {}).get("lastPrice"),
            "Market Cap": screener_data.get("Market Cap"),
            # P/E: Prefer Screener, Fallback to NSE Sector P/E
            "Stock P/E": screener_data.get("Stock P/E") or nse_data.get("metadata", {}).get("pdSectorPe"),
            "PEG Ratio": screener_data.get("PEG Ratio"),
            "ROCE": screener_data.get("ROCE"),
            "ROE": screener_data.get("ROE"),
            # High/Low: Prefer Screener, Fallback to NSE Intraday
            "High": screener_data.get("High") or nse_data.get("priceInfo", {}).get("intraDayHighLow", {}).get("max"),
            "Low": screener_data.get("Low") or nse_data.get("priceInfo", {}).get("intraDayHighLow", {}).get("min"),
            "Data Source": "Screener+NSE"
        }

        return final_record

    except Exception as e:
        logger.error(f"Failed to process {symbol}: {e}")
        return {"Symbol": symbol, "Sector": symbol_data.get("sector"), "Error": str(e), "Data Source": "Error"}

    finally:
        if browser: browser.quit()
        session.close()

# --- Main Loading Logic (Unchanged) ---

def extract_symbols_from_json(file_path: str) -> List[Dict]:
    """Parses the nested JSON structure to get a flat list of symbols."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return []

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        flat_list = []
        for tier in ["tier_1", "tier_2", "tier_3"]:
            if tier in data:
                for category, items in data[tier].items():
                    if isinstance(items, list):
                        flat_list.extend(items)

        seen = set()
        unique_list = []
        for item in flat_list:
            symbol = item.get('symbol')
            if symbol and symbol not in seen:
                seen.add(symbol)
                if 'sector' not in item:
                    item['sector'] = 'Unknown'
                unique_list.append(item)

        logger.info(f"Loaded {len(unique_list)} unique symbols from {file_path}")
        return unique_list
    except Exception as e:
        logger.error(f"Error reading JSON: {e}")
        return []

def main():
    # 1. Load Symbols
    symbols = extract_symbols_from_json("symbols.json")
    if not symbols:
        return

    results = []

    print(f"🚀 Starting scrape for {len(symbols)} symbols...")

    # 2. Parallel Execution
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(process_symbol, sym): sym for sym in symbols}

        for future in as_completed(future_map):
            res = future.result()

            # Check for generic errors before processing
            if res and "Error" not in res:
                results.append(res)

                # 3. Real-time Flushing (Polars FIX)
                try:
                    columns = ["Symbol", "Sector", "Current Price", "Market Cap", "Stock P/E", "PEG Ratio", "ROCE", "ROE", "High", "Low", "Data Source"]

                    schema_types = {
                        "Symbol": pl.String, "Sector": pl.String, "Current Price": pl.Float64,
                        "Market Cap": pl.Float64, "Stock P/E": pl.Float64, "PEG Ratio": pl.Float64,
                        "ROCE": pl.Float64, "ROE": pl.Float64, "High": pl.Float64, "Low": pl.Float64,
                        "Data Source": pl.String
                    }

                    data_row = {k: res.get(k) for k in columns}

                    df_chunk = pl.DataFrame([data_row], schema=schema_types)

                    if not os.path.exists(OUTPUT_FILE_CSV):
                        df_chunk.write_csv(OUTPUT_FILE_CSV)
                    else:
                        with open(OUTPUT_FILE_CSV, "ab") as f:
                            df_chunk.write_csv(f, include_header=False)
                    print(f"✅ Saved {res['Symbol']} (P/E: {res.get('Stock P/E')}, MCap: {res.get('Market Cap')})")

                except Exception as e:
                    logger.error(f"Save error: {e}")

    # 4. Final Consolidation
    if results:
        final_df = pl.DataFrame(results)
        final_df.write_json(OUTPUT_FILE_JSON)
        final_df.write_parquet(OUTPUT_FILE_PARQUET)
        print(f"\n🎉 Done! Scraped {len(results)} symbols.")
        print(f"Files saved: {OUTPUT_FILE_CSV}, {OUTPUT_FILE_JSON}, {OUTPUT_FILE_PARQUET}")
    else:
        print("❌ No data successfully scraped.")

if __name__ == "__main__":
    main()
