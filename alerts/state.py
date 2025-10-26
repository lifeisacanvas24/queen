#!/usr/bin/env python3
# ============================================================
# queen/alerts/state.py — v0.1 (persistent cooldown state)
# ============================================================
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from queen.settings.settings import alert_path_state

# (symbol, rule) -> last_fire_ts (float monotonic seconds)
CooldownMap = Dict[Tuple[str, str], float]


def _key(sym: str, rule: str) -> str:
    return f"{sym}::{rule}"


def load_cooldowns() -> CooldownMap:
    """Load cooldowns from state JSONL (latest wins)."""
    path: Path = alert_path_state()
    if not path.exists():
        return {}
    data: CooldownMap = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                sym = obj.get("symbol")
                rule = obj.get("rule")
                t = float(obj.get("last_fire_ts", 0.0))
                if sym and rule:
                    data[(sym, rule)] = t
            except Exception:
                # ignore bad lines
                continue
    return data


def save_cooldown(sym: str, rule: str, last_fire_ts: float) -> None:
    """Append a single cooldown record (append-only JSONL)."""
    path: Path = alert_path_state()
    rec = {
        "symbol": sym,
        "rule": rule,
        "last_fire_ts": float(last_fire_ts),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
