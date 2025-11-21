import polars as pl
import asyncio
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
import logging
from playwright.async_api import async_playwright
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class StockData:
    scripcd: str
    company_name: Optional[str] = None
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[str] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    week_high: Optional[float] = None
    week_low: Optional[float] = None
    error: Optional[str] = None

class BSEHeadlessScraper:
    def __init__(self, max_workers: int = 5, headless: bool = True):
        self.max_workers = max_workers
        self.headless = headless
        self.results_queue = Queue()
        self.failed_scrips = Queue()

    async def setup_browser(self):
        """Setup playwright browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

    async def close_browser(self):
        """Close browser resources"""
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    def clean_numeric_value(self, value: str) -> Optional[float]:
        """Clean and convert numeric values from string"""
        if not value or value == '-' or value.strip() == '':
            return None

        try:
            # Remove commas and any non-numeric characters except decimal point and minus
            cleaned = re.sub(r'[^\d.-]', '', value.strip())
            if cleaned and cleaned != '-':
                return float(cleaned)
            return None
        except (ValueError, TypeError):
            return None

    def clean_volume_value(self, value: str) -> Optional[int]:
        """Clean volume values that might have 'L' for lakhs or 'Cr' for crores"""
        if not value or value == '-' or value.strip() == '':
            return None

        try:
            value = value.strip().upper()
            if 'CR' in value:
                # Convert crores to actual number
                num = float(re.sub(r'[^\d.]', '', value))
                return int(num * 10000000)
            elif 'L' in value:
                # Convert lakhs to actual number
                num = float(re.sub(r'[^\d.]', '', value))
                return int(num * 100000)
            else:
                # Regular number with commas
                return int(re.sub(r'[^\d]', '', value))
        except (ValueError, TypeError):
            return None

    async def scrape_single_stock(self, scripcd: str) -> StockData:
        """Scrape data for a single stock"""
        stock_data = StockData(scripcd=scripcd)

        try:
            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()

            url = f"https://m.bseindia.com/StockReach.aspx?scripcd={scripcd}"
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for key elements to load
            await page.wait_for_selector('table', timeout=10000)

            # Extract company name
            name_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_CompanyName')
            if name_element:
                stock_data.company_name = await name_element.text_content()

            # Extract current price
            price_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lblCurr')
            if price_element:
                price_text = await price_element.text_content()
                stock_data.current_price = self.clean_numeric_value(price_text)

            # Extract previous close
            prev_close_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lblPrev')
            if prev_close_element:
                prev_text = await prev_close_element.text_content()
                stock_data.previous_close = self.clean_numeric_value(prev_text)

            # Extract change and percentage change
            change_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lblChange')
            if change_element:
                change_text = await change_element.text_content()
                if change_text and '(' in change_text and ')' in change_text:
                    # Extract absolute change and percentage change
                    parts = change_text.split('(')
                    if len(parts) == 2:
                        abs_change = parts[0].strip()
                        perc_change = parts[1].replace(')', '').replace('%', '').strip()
                        stock_data.change = self.clean_numeric_value(abs_change)
                        stock_data.change_percent = self.clean_numeric_value(perc_change)

            # Extract volume
            volume_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lblVol')
            if volume_element:
                volume_text = await volume_element.text_content()
                stock_data.volume = self.clean_volume_value(volume_text)

            # Extract day high/low
            day_high_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lblHgh')
            if day_high_element:
                day_high_text = await day_high_element.text_content()
                stock_data.day_high = self.clean_numeric_value(day_high_text)

            day_low_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lblLow')
            if day_low_element:
                day_low_text = await day_low_element.text_content()
                stock_data.day_low = self.clean_numeric_value(day_low_text)

            # Extract 52-week high/low
            week_high_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lbl52H')
            if week_high_element:
                week_high_text = await week_high_element.text_content()
                stock_data.week_high = self.clean_numeric_value(week_high_text)

            week_low_element = await page.query_selector('span#ctl00_ContentPlaceHolder1_lbl52L')
            if week_low_element:
                week_low_text = await week_low_element.text_content()
                stock_data.week_low = self.clean_numeric_value(week_low_text)

            # Extract market cap
            market_cap_element = await page.query_selector('//td[contains(text(), "Market Cap")]/following-sibling::td')
            if market_cap_element:
                market_cap_text = await market_cap_element.text_content()
                if market_cap_text:
                    stock_data.market_cap = market_cap_text.strip()

            await context.close()

        except Exception as e:
            stock_data.error = f"Scraping failed: {str(e)}"
            logger.error(f"Error scraping {scripcd}: {str(e)}")
            self.failed_scrips.put(scripcd)

        return stock_data

    async def scrape_stocks_async(self, scripcds: List[str]) -> List[StockData]:
        """Scrape multiple stocks asynchronously"""
        tasks = []
        for scripcd in scripcds:
            task = self.scrape_single_stock(scripcd)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return valid results
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async task failed: {result}")
            else:
                valid_results.append(result)

        return valid_results

    def stock_data_to_dict(self, stock_data: StockData) -> Dict[str, Any]:
        """Convert StockData object to dictionary"""
        return {
            'scripcd': stock_data.scripcd,
            'company_name': stock_data.company_name,
            'current_price': stock_data.current_price,
            'previous_close': stock_data.previous_close,
            'change': stock_data.change,
            'change_percent': stock_data.change_percent,
            'volume': stock_data.volume,
            'market_cap': stock_data.market_cap,
            'day_high': stock_data.day_high,
            'day_low': stock_data.day_low,
            'week_high': stock_data.week_high,
            'week_low': stock_data.week_low,
            'error': stock_data.error,
            'scraped_at': pl.datetime.now()
        }

class PolarsDataProcessor:
    """Polars-centric data processor"""

    def __init__(self):
        self.schema = {
            'scripcd': pl.Utf8,
            'company_name': pl.Utf8,
            'current_price': pl.Float64,
            'previous_close': pl.Float64,
            'change': pl.Float64,
            'change_percent': pl.Float64,
            'volume': pl.Int64,
            'market_cap': pl.Utf8,
            'day_high': pl.Float64,
            'day_low': pl.Float64,
            'week_high': pl.Float64,
            'week_low': pl.Float64,
            'error': pl.Utf8,
            'scraped_at': pl.Datetime
        }

    def create_dataframe(self, data: List[Dict[str, Any]]) -> pl.DataFrame:
        """Create Polars DataFrame from scraped data"""
        if not data:
            return pl.DataFrame(schema=self.schema)

        df = pl.DataFrame(data, schema=self.schema)
        return df

    def save_to_parquet(self, df: pl.DataFrame, filename: str):
        """Save DataFrame to Parquet format"""
        df.write_parquet(filename)
        logger.info(f"Data saved to {filename}")

    def save_to_csv(self, df: pl.DataFrame, filename: str):
        """Save DataFrame to CSV format"""
        df.write_csv(filename)
        logger.info(f"Data saved to {filename}")

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Perform data analysis on the scraped data"""
        analysis = df.select([
            pl.col('current_price').mean().alias('avg_price'),
            pl.col('volume').mean().alias('avg_volume'),
            pl.col('change_percent').mean().alias('avg_change_percent'),
            pl.col('current_price').max().alias('max_price'),
            pl.col('current_price').min().alias('min_price')
        ])
        return analysis

async def main():
    """Main execution function"""

    # Load scrip codes from JSON file
    try:
        with open('scrip_codes.json', 'r') as f:
            scrip_data = json.load(f)
        scripcds = [item['scripcd'] for item in scrip_data]
        logger.info(f"Loaded {len(scripcds)} scrip codes from JSON file")
    except FileNotFoundError:
        logger.error("scrip_codes.json file not found")
        return
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in scrip_codes.json")
        return

    # Initialize scraper and processor
    scraper = BSEHeadlessScraper(max_workers=5, headless=True)
    processor = PolarsDataProcessor()

    try:
        # Setup browser
        await scraper.setup_browser()
        logger.info("Browser setup completed")

        # Scrape data
        logger.info("Starting data scraping...")
        start_time = time.time()

        # Scrape in batches to avoid overwhelming the server
        batch_size = 3
        all_results = []

        for i in range(0, len(scripcds), batch_size):
            batch = scripcds[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(scripcds)-1)//batch_size + 1}")

            batch_results = await scraper.scrape_stocks_async(batch)
            all_results.extend(batch_results)

            # Add delay between batches to be respectful to the server
            if i + batch_size < len(scripcds):
                await asyncio.sleep(2)

        # Convert to dictionaries
        data_dicts = [scraper.stock_data_to_dict(result) for result in all_results]

        # Process data with Polars
        df = processor.create_dataframe(data_dicts)

        # Display results
        print("\n" + "="*80)
        print("SCRAPING RESULTS SUMMARY")
        print("="*80)
        print(f"Total stocks processed: {len(df)}")
        print(f"Successful scrapes: {len(df.filter(pl.col('error').is_null()))}")
        print(f"Failed scrapes: {len(df.filter(pl.col('error').is_not_null()))}")

        # Show successful results
        successful_df = df.filter(pl.col('error').is_null())
        if len(successful_df) > 0:
            print(f"\nSUCCESSFUL SCRAPES ({len(successful_df)}):")
            print(successful_df.select(['scripcd', 'company_name', 'current_price', 'change_percent']))

        # Show failed results
        failed_df = df.filter(pl.col('error').is_not_null())
        if len(failed_df) > 0:
            print(f"\nFAILED SCRAPES ({len(failed_df)}):")
            print(failed_df.select(['scripcd', 'error']))

        # Save results
        timestamp = pl.datetime.now().strftime("%Y%m%d_%H%M%S")
        processor.save_to_parquet(df, f'bse_stock_data_{timestamp}.parquet')
        processor.save_to_csv(df, f'bse_stock_data_{timestamp}.csv')

        # Perform analysis
        analysis = processor.analyze_data(successful_df)
        print(f"\nDATA ANALYSIS:")
        print(analysis)

        elapsed_time = time.time() - start_time
        print(f"\nTotal execution time: {elapsed_time:.2f} seconds")

    except Exception as e:
        logger.error(f"Main execution failed: {str(e)}")

    finally:
        # Cleanup
        await scraper.close_browser()

if __name__ == "__main__":
    asyncio.run(main())
