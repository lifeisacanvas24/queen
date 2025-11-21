#!/usr/bin/env python3
# ============================================================
# quant/utils/convert_instruments_to_master.py — v1.6 FINAL
# ============================================================
"""Convert NSE raw equity CSV → master_active_list.json (Config-Driven)
-------------------------------------------------------------------------
Uses Quant-Core’s unified config.py:
    ✅ Reads NSE source file path from data_config.json
    ✅ Writes generated files under ./data/static/generated/
    ✅ Skips junk / SME / BE / ST / delisted entries
    ✅ Adds metadata (timestamp, counts, version)
"""

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from quant import config
from quant.utils.logs import auto_logger

logger = auto_logger("ConvertInstruments")

# ============================================================
# ⚙️ CONFIG BINDINGS
# ============================================================
NSE_CSV = config.get_path("paths.nse_all_symbols_file")
MASTER_JSON = config.get_path("paths.master_active_list")
SKIPPED_JSON = config.get_path("paths.skipped_list")

VALID_SERIES = {"EQ"}  # only EQ segment
JUNK_SERIES = {"SM", "BE", "BZ", "ST", "P1", "P2", "GS"}
EXCHANGE_PREFIX = "NSE_EQ|"
EXCHANGE_NAME = "NSE"


# ============================================================
# 🧠 Helpers
# ============================================================
def normalize_date(date_str: str) -> str | None:
    """Convert '06-OCT-2008' → '2008-10-06'."""
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str.strip(), "%d-%b-%Y")
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None


# ============================================================
# 🧩 Parser
# ============================================================
def parse_nse_equity_file(file_path: Path):
    if not file_path.exists():
        raise FileNotFoundError(f"❌ Missing NSE source file: {file_path}")

    active, skipped = [], []
    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean_row = {k.strip().upper(): v.strip() for k, v in row.items() if k}
            symbol = clean_row.get("SYMBOL", "")
            isin_raw = clean_row.get("ISIN NUMBER", "")
            series = clean_row.get("SERIES", "")
            listing_date = normalize_date(clean_row.get("DATE OF LISTING", ""))

            if not symbol or not isin_raw:
                continue
            if series not in VALID_SERIES or series in JUNK_SERIES:
                skipped.append(
                    {"symbol": symbol, "series": series, "reason": "Invalid or non-EQ"}
                )
                continue

            isin = f"{EXCHANGE_PREFIX}{isin_raw}"
            entry = {"symbol": symbol, "isin": isin}
            if listing_date:
                entry["listing_date"] = listing_date
            active.append(entry)

    return active, skipped


# ============================================================
# 📜 Summary Printer
# ============================================================
def print_summary(active, skipped):
    total = len(active) + len(skipped)
    print(f"\n📊 {EXCHANGE_NAME} Conversion Summary")
    print("━" * 60)
    print(f"Total symbols: {total}")
    print(f"✅ Active (EQ): {len(active)}")
    print(f"🗑️ Skipped (non-EQ): {len(skipped)}")
    if skipped:
        counts = Counter([s.get("series", "UNK") for s in skipped])
        print("\nTop skipped series:")
        for s, n in counts.items():
            print(f"  • {s:<4} → {n}")
    print("━" * 60)


# ============================================================
# 🚀 MAIN BUILDER
# ============================================================
def build_master_list():
    logger.info("🚀 Starting NSE master list build...")
    active, skipped = parse_nse_equity_file(NSE_CSV)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "exchange": EXCHANGE_NAME,
        "source_file": str(NSE_CSV.name),
        "active_count": len(active),
        "skipped_count": len(skipped),
        "version": "1.6",
    }

    MASTER_JSON.parent.mkdir(parents=True, exist_ok=True)
    MASTER_JSON.write_text(
        json.dumps({"meta": meta, "data": active}, indent=2, ensure_ascii=False)
    )
    SKIPPED_JSON.write_text(json.dumps(skipped, indent=2, ensure_ascii=False))

    print_summary(active, skipped)
    logger.info(f"✅ Master written → {MASTER_JSON}")
    logger.info(f"🗑️ Skipped list → {SKIPPED_JSON}")


if __name__ == "__main__":
    build_master_list()
