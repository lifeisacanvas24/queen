import polars as pl
import asyncio
from typing import List
from bse_scraper import BSEHeadlessScraper, PolarsDataProcessor
import json
import logging

class BatchStockProcessor:
    """Process large batches of stocks with progress tracking"""

    def __init__(self, batch_size: int = 5, max_concurrent: int = 3):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.scraper = BSEHeadlessScraper(max_workers=max_concurrent)
        self.processor = PolarsDataProcessor()

    async def process_large_batch(self, scripcds: List[str], output_file: str):
        """Process large batches of stock codes"""
        all_results = []

        await self.scraper.setup_browser()

        try:
            total_batches = (len(scripcds) - 1) // self.batch_size + 1

            for batch_num in range(total_batches):
                start_idx = batch_num * self.batch_size
                end_idx = min((batch_num + 1) * self.batch_size, len(scripcds))
                batch = scripcds[start_idx:end_idx]

                logging.info(f"Processing batch {batch_num + 1}/{total_batches} "
                           f"({len(batch)} stocks)")

                batch_results = await self.scraper.scrape_stocks_async(batch)
                all_results.extend(batch_results)

                # Save progress after each batch
                if all_results:
                    data_dicts = [self.scraper.stock_data_to_dict(result)
                                for result in all_results]
                    df = self.processor.create_dataframe(data_dicts)
                    self.processor.save_to_parquet(df, f"{output_file}_progress.parquet")

                # Rate limiting
                if batch_num < total_batches - 1:
                    await asyncio.sleep(3)

            # Final save
            data_dicts = [self.scraper.stock_data_to_dict(result)
                         for result in all_results]
            df = self.processor.create_dataframe(data_dicts)
            self.processor.save_to_parquet(df, f"{output_file}_final.parquet")
            self.processor.save_to_csv(df, f"{output_file}_final.csv")

            return df

        finally:
            await self.scraper.close_browser()

# Example usage for large datasets
async def process_large_dataset():
    """Example for processing large datasets"""

    # Load your scrip codes
    with open('scrip_codes.json', 'r') as f:
        scrip_data = json.load(f)
    scripcds = [item['scripcd'] for item in scrip_data]

    # Process in large batches
    processor = BatchStockProcessor(batch_size=10, max_concurrent=3)
    result_df = await processor.process_large_batch(scripcds, "large_batch_results")

    return result_df

if __name__ == "__main__":
    asyncio.run(process_large_dataset())
