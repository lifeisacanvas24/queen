# Queen Sim v2 — Developer Notes

This note explains the new **simulation fields**, **CLI stats**, and **knobs** so you can read outputs without guessing.

---

## 1. Row-Level Simulation Columns

Produced by `queen/services/actionable_row.py` when `pos_mode="auto"` and `auto_side="long"`.

### Core position state

- `sim_side`  
  `"FLAT"` or `"LONG"` — simulator’s current side.

- `sim_qty`  
  Position quantity (in “units”, sized via `NOTIONAL_PER_UNIT_DEFAULT`).

- `sim_avg`  
  Average price of the open position (None when flat).

- `sim_pnl`  
  **Unrealised** PnL for the bar: `(cmp - sim_avg) * sim_qty`.

- `sim_pnl_pct`  
  Unrealised PnL in %: `(cmp - sim_avg) / sim_avg * 100`.

- `sim_realized_pnl`  
  Cumulative **realised** PnL over all closed trades so far.

- `sim_total_pnl`  
  `sim_pnl + sim_realized_pnl` — total PnL including open trade.

- `sim_unit_size`  
  Price-based unit size for this symbol:
  ~ `NOTIONAL_PER_UNIT_DEFAULT / cmp`, clamped to `[1, max_units]`.

### Peak / trailing

- `sim_peak`  
  Highest simulated price seen since the current trade opened.

- `sim_trail_stop`  
  Dynamic trailing stop: `sim_peak * (1 - TRAIL_PCT)`.

- `sim_exit_reason`
  - `"TRAILING_STOP"` — exit by trail.
  - `"HARD_EXIT"` — explicit EXIT / AVOID / trade_status EXIT.
  - `"EOD_FORCED"` — forced exit because `eod_force=True`.

- `sim_forced_eod`  
  `True` iff the exit happened due to EOD force.

### Signal vs simulator

- `decision` (existing)  
  Raw signal coming from fusion (`BUY`, `ADD`, `EXIT`, `NO_ACTION`, …).

- `sim_effective_decision`  
  What the **simulator actually did** after applying its rules:
  - `"BUY"` / `"ADD"` — position open / pyramid.
  - `"EXIT"` — position closed (trail / hard / EOD).
  - `"NO_ACTION"` — simulator ignored the signal.

- `sim_ignored_signal` (`bool`)  
  `True` when the **incoming signal was ignored** by sim rules  
  (currently only ADD filters: not green enough / below `ADD_MIN_UNREAL_PCT`).

- `sim_skipped_add` (`int`)  
  `1` if an ADD was skipped due to rules on this bar, else `0`.

- `sim_skip_reason` (`str | None`)  
  Human reason for skip. e.g. `"ADD_SKIPPED_BY_RULE"`.

### Trade identity

- `sim_trade_id` (`int | None`)
  - Assigned on **entry bar** for each trade (`1, 2, 3, …`).
  - Present on **all bars during a trade** (including exit bar).
  - `None` on bars outside trades.
  - Used by `sim_stats.py` to compute per-trade PnL and skipped_adds.

---

## 2. CLI Stats (`queen/cli/sim_stats.py`)

Run:

```bash
python -m queen.cli.sim_stats --parquet path/to/scan_signals.parquet
# Optional:
#   --symbol-filter SMLMAH GRSE ...
```

python -m queen.cli.scan_signals \
 --symbols SMLMAH \
 --interval 15 \
 --book all \
 --out-parquet /tmp/smlmah_15m.parquet

python -m queen.cli.sim_stats \
 --parquet /tmp/smlmah_15m.parquet \
 --symbol-filter SMLMAH

python -m queen.cli.debug_decisions \
 --symbol SMLMAH \
 --interval 15 \
 --book all \
 --warmup 1

Nice, this is a perfect place to “lock in” the sim tooling before we move on 🧠⚙️

I’ll do both: 1. End-to-end debug_decisions.py updated to show all key sim columns. 2. A sim sanity checklist you can reuse for any symbol / parquet run.

No fallbacks, no hidden behaviour.

⸻

1️⃣ Full queen/cli/debug_decisions.py

Replace your existing queen/cli/debug_decisions.py completely with this:

#!/usr/bin/env python3

# ============================================================

# queen/cli/debug_decisions.py — v1.0 (Sim-aware)

# ------------------------------------------------------------

# Bar-by-bar debug view:

# • raw decision / action_tag / playbook

# • sim_effective_decision / sim_ignored_signal

# • sim position state, PnL, trail, trade_id

#

# Example:

# python -m queen.cli.debug_decisions --symbol SMLMAH --interval 15

# ============================================================

from **future** import annotations

import argparse
import asyncio
from typing import Any, Dict

import polars as pl

from queen.cli.replay_actionable import ReplayConfig, replay_actionable
from queen.helpers.logger import log

def main() -> None:
parser = argparse.ArgumentParser(
description="Debug decision/action_tag + simulator stream for a symbol."
)
parser.add_argument("--symbol", required=True, help="Symbol, e.g. FORCEMOT")
parser.add_argument(
"--interval",
type=int,
default=15,
help="Intraday interval in minutes (default: 15).",
)
parser.add_argument(
"--book",
type=str,
default="all",
help="Book name (default: all).",
)
parser.add_argument(
"--warmup",
type=int,
default=1,
help="Warmup bars before emitting rows (default: 1).",
)
parser.add_argument(
"--date-from",
type=str,
default=None,
help="Optional start date (YYYY-MM-DD).",
)
parser.add_argument(
"--date-to",
type=str,
default=None,
help="Optional end date (YYYY-MM-DD).",
)
args = parser.parse_args()

    sym = args.symbol.upper()
    cfg = ReplayConfig(
        symbol=sym,
        date_from=args.date_from,
        date_to=args.date_to,
        interval_min=args.interval,
        book=args.book,
        warmup=args.warmup,
        final_only=False,
        pos_mode="auto",
        auto_side="long",
    )

    log.info(
        f"[DebugDecisions] Replaying {sym} @ {args.interval}m "
        f"(book={args.book}, warmup={args.warmup}, "
        f"from={args.date_from}, to={args.date_to})"
    )

    payload: Dict[str, Any] = asyncio.run(replay_actionable(cfg))
    rows = payload.get("rows") or []
    if not rows:
        print("[DebugDecisions] No rows returned.")
        return

    df = pl.DataFrame(rows)

    if "timestamp" in df.columns:
        df = df.sort("timestamp")

    # Columns we *want* to see if present.
    wanted = [
        # Time & signal
        "timestamp",
        "decision",
        "sim_effective_decision",
        "sim_ignored_signal",
        "action_tag",
        "playbook",
        "time_bucket",
        # Context / trend
        "trend_bias",
        "trend_score",
        "vwap_zone",
        # Prices
        "cmp",
        "entry",
        # Sim position state
        "sim_side",
        "sim_qty",
        "sim_avg",
        "sim_pnl",
        "sim_pnl_pct",
        "sim_realized_pnl",
        "sim_total_pnl",
        "sim_unit_size",
        # Trade identity
        "sim_trade_id",
        # Add rules & diagnostics
        "sim_skipped_add",
        "sim_skip_reason",
        "sim_trail_stop",
        "sim_peak",
        # Exit diagnostics
        "sim_exit_reason",
        "sim_forced_eod",
    ]

    cols = [c for c in wanted if c in df.columns]
    df = df.select(cols)

    print("\n=== Decision Stream Debug ===")
    print(df)
    print("================================\n")

if **name** == "**main**":
main()

What’s new compared to your earlier version:
• Imports asyncio at top and uses it directly (no try/except fallback).
• Shows:
• sim_effective_decision
• sim_ignored_signal
• sim_trade_id
• sim_trail_stop
• sim_peak
• sim_skipped_add
• sim_skip_reason
• sim_pnl_pct
• sim_unit_size
• sim_exit_reason
• sim_forced_eod

So a single run gives you full story per bar.

⸻

2️⃣ Sim sanity checklist (reusable)

Here’s a small checklist you can keep (copy it into a SIM_CHECKLIST.md if you want). Use it whenever you:
• tweak knobs in sim_settings.py, or
• refactor sim logic, or
• want to validate behaviour for a given symbol.

I’ll assume:
• You run scan_signals to generate a parquet.
• Then you run sim_stats.py and debug_decisions.py on that parquet / symbol.

⸻

✅ Step 1 — Generate a fresh scan

Pick a symbol and interval you know is “interesting” (like SMLMAH 15m):

# Example

python -m queen.cli.scan_signals \
 --symbols SMLMAH LTIM LTTS \
 --interval 15 \
 --book all \
 --out /tmp/smlmah_15m.parquet

⸻

✅ Step 2 — High-level stats sanity

Run the sim stats CLI on the parquet:

python -m queen.cli.sim_stats --parquet queen/data/runtime/dev/scan_signals_live_intraday_15m.parquet --symbol-filter SMLMAH LTIM LTTS

Verify: 1. Trades / PnL:
• trades > 0 (for a busy symbol).
• realized_pnl matches value you see in debug_decisions on the last row’s sim_realized_pnl. 2. Drawdown:
• max_drawdown is ≤ 0 (drawdown is negative or zero).
• If max_drawdown is 0 but you see equity going up and down in rows → something’s off. 3. Skipped adds / ignored signals:
• skipped_adds ≈ number of bars where decision = ADD but sim rules blocked it.
• skipped_adds_in_trades should be:
• > 0 if you have many skipped ADDs while in positions.
• skipped_adds_outside_trades:
• usually small; if huge, check why you are getting ADDs when flat. 4. Ignored signals:
• ignored_signals should roughly match “number of ADDs that didn’t pass rules”.
• Compare with sim_summary (by sim_effective_decision):
• If many raw ADD but very few effective ADD, you expect a lot of NO_ACTION in sim summary.

⸻

✅ Step 3 — Per-trade breakdown sanity

In sim_stats.py output, look at:

--- Trades for SMLMAH (count=1) ---
T1: pnl=-569.20 skipped_adds=48 (rows=50)

Check: 1. Trade count:
• count here must equal trades in the symbol table. 2. Trade PnL:
• pnl for each Tn should sum up to final realized_pnl in the per-symbol table
(sum of all trades’ pnl). 3. Skipped adds per trade:
• If skipped_adds is huge (like 48), that means:
• Most ADD signals during that trade were blocked by rules.
• Tweak ADD_MIN_UNREAL_PCT and/or ADD_ONLY_WHEN_GREEN and rerun to see the number drop or rise.

⸻

✅ Step 4 — Bar-by-bar sanity with debug_decisions.py

Run:

python -m queen.cli.debug_decisions \
 --symbol SMLMAH LTIM LTTS \
 --interval 15 \
 --book all \
 --warmup 1

Now visually check: 1. Entry bar:
• First row where sim_side becomes "LONG":
• sim_effective_decision should be "BUY".
• sim_trade_id should become 1.
• sim_unit_size > 0.
• sim_avg ≈ entry on that bar. 2. During trade:
• sim_side == "LONG".
• sim_trade_id == 1 (same id for all bars until exit).
• For every bar:
• sim_total_pnl = sim_realized_pnl + sim_pnl
(or close, if you check manually). 3. ADD behaviour:
• Find rows where decision == "ADD":
• If ADD passes rules:
• sim_effective_decision == "ADD".
• sim_ignored_signal == False.
• sim_skipped_add == 0.
• sim_qty should increase vs previous bar.
• If ADD is blocked:
• sim_effective_decision == "NO_ACTION".
• sim_ignored_signal == True.
• sim_skipped_add == 1.
• sim_skip_reason == "ADD_SKIPPED_BY_RULE".
• sim_qty does not change. 4. Trailing stop:
• If exit happens via trailing stop:
• On the exit bar:
• sim_exit_reason == "TRAILING_STOP".
• sim_forced_eod == False.
• sim_side goes "LONG" → "FLAT".
• sim_trade_id becomes None (or 0) on subsequent bars. 5. Hard / EOD exit:
• If exit is due to decision == EXIT / AVOID or eod_force=True:
• sim_exit_reason should be "HARD_EXIT" or "EOD_FORCED" respectively.
• sim_forced_eod should match (True only for EOD forced).

⸻

✅ Step 5 — Knob tuning loop

When you change knobs in sim_settings.py, follow this loop: 1. Change one or two knobs, e.g.:

NOTIONAL_PER_UNIT_DEFAULT = 5_000.0
MAX_PYRAMID_UNITS = 3.0
ADD_MIN_UNREAL_PCT = 2.0

    2.	Run:

python -m queen.cli.scan_signals ... # regenerate parquet
python -m queen.cli.sim_stats --parquet ... --symbol-filter SMLMAH
python -m queen.cli.debug_decisions --symbol SMLMAH --interval 15

    3.	Re-check:
    •	trades, win_rate, max_drawdown.
    •	skipped_adds, skipped_adds_in_trades.
    •	Sim behaviour on entry/exit/ADD with debug_decisions.py.

Do that for 1–3 different symbols (e.g. one trend, one choppy, one flat), and if all looks logical, the sim is in a very good place.

⸻

If you want, next we can:
• Capture this checklist + a couple of example outputs into a SIM_PLAYBOOK.md,
• Or move on to the next roadmap item (e.g. risk modes, multi-side sim, or better dashboards).
