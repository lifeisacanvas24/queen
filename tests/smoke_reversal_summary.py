#!/usr/bin/env python3
from __future__ import annotations

import polars as pl
from queen.technicals.signals.reversal_summary import summarize_reversal_stacks


def main():
    dfs = {
        "15m": pl.DataFrame(
            {
                "Reversal_Stack_Alert": ["—", "Potential BUY", "BUY"],
                "Reversal_Score": [0.1, 0.6, 0.9],
            }
        ),
        "1h": pl.DataFrame(
            {
                "Reversal_Stack_Alert": ["—", "Potential SELL", "SELL"],
                "Reversal_Score": [0.2, 0.55, 0.8],
            }
        ),
    }
    summarize_reversal_stacks(dfs)
    print("✅ smoke_reversal_summary: rendered without errors")


if __name__ == "__main__":
    main()
