#!/usr/bin/env python3
# tools/smoke_test_sim.py
"""Quick local smoke test for the simulator functions with artificial rows.

Usage: python tools/smoke_test_sim.py
"""

from __future__ import annotations

from pprint import pprint

from queen.services.actionable_row import _step_auto_long_sim, _compute_unit_size

# Create a tiny synthetic stream: entry at 100, a few ADDs when price drops, price recovers, trailing stop
rows = [
    {"timestamp": "t0", "decision": "BUY", "cmp": 100.0, "entry": 100.0},
    {"timestamp": "t1", "decision": "ADD", "cmp": 95.0, "entry": 95.0},
    {"timestamp": "t2", "decision": "ADD", "cmp": 90.0, "entry": 90.0},
    {"timestamp": "t3", "decision": "ADD", "cmp": 110.0, "entry": 110.0},
    {"timestamp": "t4", "decision": "EXIT", "cmp": 108.0, "entry": 108.0},
]

sim_state = None
print("Smoke test: running sim through small stream")
for r in rows:
    r_out, sim_state = _step_auto_long_sim(r.copy(), sim_state, eod_force=False)
    print("row:", r_out.get("timestamp"), "->", r_out.get("sim_effective_decision"),
          "trade_id:", r_out.get("sim_trade_id"),
          "ignored:", r_out.get("sim_ignored_signal"),
          "skipped_add:", r_out.get("sim_skipped_add"),
          "sim_qty:", r_out.get("sim_qty"),
          "sim_avg:", r_out.get("sim_avg"),
          "sim_pnl:", r_out.get("sim_pnl"))
print("final sim_state:", sim_state)
