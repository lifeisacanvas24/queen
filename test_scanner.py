#!/usr/bin/env python3
# ============================================================
# test_scanner.py — Quick validation script
# ============================================================
"""Test the scanner with a small symbol set"""

import subprocess
import sys
from pathlib import Path

def main():
    # Create a small test CSV with large-cap stocks
    test_symbols = """SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE
RELIANCE,Reliance Industries Ltd,EQ,29-NOV-2006,507,1,INE002A01018,10
TCS,Tata Consultancy Services,EQ,25-AUG-2004,220,1,INE467B01029,1
INFY,Infosys Limited,EQ,08-NOV-1995,220,1,INE009A01021,5
HDFCBANK,HDFC Bank Limited,EQ,23-NOV-1995,550,1,INE040A01034,1
ICICIBANK,ICICI Bank Limited,EQ,17-JUN-1998,660,1,INE090A01021,2
SBIN,State Bank of India,EQ,01-MAR-1995,400,1,INE062A01020,1
ITC,ITC Limited,EQ,19-JUL-1995,500,1,INE154A01025,1
LT,Larsen & Toubro,EQ,23-JUN-1998,200,1,INE018A01030,2
SUNPHARMA,Sun Pharmaceutical Industries,EQ,17-NOV-1994,100,1,INE044A01036,1
"""

    test_file = Path("test_symbols.csv")
    test_file.write_text(test_symbols)

    print("🚀 Running scanner on test symbols...")
    print(f"   Test file: {test_file.absolute()}")
    print(f"   Output dir: ./test_output/")

    # Create output directory
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    # Run scanner
    cmd = [
        sys.executable, "queen/cli/universe_scanner.py",
        "--symbols", str(test_file),
        "--max", "5",
        "--concurrency", "2",
        "--output", str(output_dir)
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("\n" + "="*70)
        print("✅ TEST PASSED - Scanner completed successfully!")
        print("="*70)
        print("\n📊 Output files:")
        for f in output_dir.glob("*.csv"):
            print(f"   📄 {f.name} ({f.stat().st_size} bytes)")

        # Show first few lines of Tier 1 if exists
        tier1_file = output_dir / "tier_1_intraday_core_.csv"
        if tier1_file.exists():
            print(f"\n🎯 Sample Tier 1 output:")
            print(tier1_file.read_text()[:500])

    except subprocess.CalledProcessError as e:
        print(f"\n❌ TEST FAILED")
        print(f"   Exit code: {e.returncode}")
        print(f"   Stderr: {e.stderr}")
        sys.exit(1)
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
            print(f"\n🧹 Cleaned up test file: {test_file.name}")

        # Don't clean output dir so user can inspect

    print("\n🎉 Test complete! Check ./test_output/ for results.")


if __name__ == "__main__":
    main()
