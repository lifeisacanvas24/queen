#!/usr/bin/env python3
# ============================================================
# queen/meta/strategy_cycle.py — v1.0 (Meta → Strategy snapshot)
# ============================================================
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import polars as pl

# strategy
from queen.strategies.fusion import run_strategy


# ---------- path resolver (settings-aware, no circular imports) ----------
def _resolve_logs_dir() -> Path:
    # 1) env override
    import os

    env = os.getenv("QUEEN_LOG_DIR")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    # 2) settings-aware (import the concrete module)
    try:
        import queen.settings.settings as CFG  # type: ignore

        logs = CFG.PATHS.get("LOGS")
        if logs:
            p = Path(logs)
            p.mkdir(parents=True, exist_ok=True)
            return p
    except Exception:
        pass
    # 3) fallback
    p = Path("queen/data/runtime/logs")
    p.mkdir(parents=True, exist_ok=True)
    return p


LOGS_DIR = _resolve_logs_dir()
CSV_PATH = LOGS_DIR / "tactical_snapshot.csv"
JSONL_PATH = LOGS_DIR / "tactical_snapshot.jsonl"


# ---------- tiny utils ----------
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_df(obj) -> pl.DataFrame:
    return obj if isinstance(obj, pl.DataFrame) else pl.DataFrame(obj)


# ---------- public API ----------
def run_meta_cycle(symbol: str, frames: Dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Run one strategy cycle for `symbol` across provided TF frames and persist a flat snapshot."""
    out = run_strategy(symbol, frames)
    rows = []
    for tf, row in out["per_tf"].items():
        # read passthroughs when present in source frames
        src = frames.get(tf)
        regime = None
        rstack = None
        tindex = None
        atr_ratio = None
        if isinstance(src, pl.DataFrame) and not src.is_empty():
            # take last values if columns exist
            def _last(col: str):
                try:
                    return src.get_column(col).tail(1).item()
                except Exception:
                    return None

            regime = _last("Regime_State")
            rstack = _last("Reversal_Stack_Alert")
            tindex = _last("Tactical_Index")
            atr_ratio = _last("ATR_Ratio")
        rows.append(
            {
                "timestamp": _utc_now_iso(),
                "symbol": symbol,
                "timeframe": tf,
                "strategy_score": row["strategy_score"],
                "bias": row["bias"],
                "entry_ok": row["entry_ok"],
                "exit_ok": row["exit_ok"],
                "risk_band": row["risk_band"],
                "Regime_State": regime,
                "Reversal_Stack_Alert": rstack,
                "Tactical_Index": tindex,
                "ATR_Ratio": atr_ratio,
            }
        )

    df = pl.DataFrame(rows)

    # append CSV (create if missing)
    if CSV_PATH.exists():
        old = pl.read_csv(CSV_PATH)
        df = pl.concat([old, df], how="vertical_relaxed")
    df.write_csv(CSV_PATH)

    # append JSONL
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return _ensure_df(rows)
