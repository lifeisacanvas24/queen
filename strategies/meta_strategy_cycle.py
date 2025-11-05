#!/usr/bin/env python3
# ============================================================
# queen/strategies/meta_strategy_cycle.py — v1.2
# Produce tactical snapshots (per symbol × timeframe) using fusion strategy
# ============================================================
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import polars as pl
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS
from queen.helpers import io
from queen.strategies.fusion import run_strategy


# ------------------------------------------------------------
# 📋 Schema definition (single source of truth)
# ------------------------------------------------------------
SNAPSHOT_COLS = [
    "timestamp",
    "symbol",
    "timeframe",
    "Tactical_Index",
    "strategy_score",
    "bias",
    "entry_ok",
    "exit_ok",
    "risk_band",
    "Regime_State",
    "ATR_Ratio",
    "SPS",
]

# sensible defaults for any missing snapshot cols
_SNAPSHOT_DEFAULTS: dict[str, Any] = {
    "timestamp": None,  # keep row's own ts if present
    "symbol": "",
    "timeframe": "",
    "Tactical_Index": 0.0,
    "strategy_score": 0.0,
    "bias": "neutral",
    "entry_ok": False,
    "exit_ok": False,
    "risk_band": "low",
    "Regime_State": "NEUTRAL",
    "ATR_Ratio": 1.0,
    "SPS": 0.0,
    # "Reversal_Stack_Alert" is intentionally defaulted to empty string:
    "Reversal_Stack_Alert": "",
}


# ------------------------------------------------------------
# 🔸 JSONL helpers
# ------------------------------------------------------------
def _append_jsonl(path: Path, record: dict) -> None:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _cap_jsonl(path: Path, max_lines: int = 5000):
    """Trim JSONL to last N lines (keeps file tidy)."""
    try:
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > max_lines:
            path.write_text("\n".join(lines[-max_lines:]) + "\n", encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------
# 🧩 Dummy OHLCV builder (for smoke/dev)
# ------------------------------------------------------------
def _dummy_ohlcv(n: int = 180) -> pl.DataFrame:
    end_ts = datetime.now(tz=timezone.utc)
    start_ts = end_ts - timedelta(minutes=n - 1)
    ts = pl.datetime_range(start=start_ts, end=end_ts, interval="1m", eager=True)

    # Safety: ensure length = n
    if len(ts) > n:
        ts = ts.tail(n)
    elif len(ts) < n:
        missing = n - len(ts)
        if missing > 0:
            last = ts[-1]
            extra = pl.datetime_range(
                start=last + timedelta(minutes=1),
                end=last + timedelta(minutes=missing),
                interval="1m",
                eager=True,
            )
            ts = pl.concat([ts, extra])

    base = 100.0
    close = [base + (i % 10) * 0.1 for i in range(n)]
    open_ = [c - 0.05 for c in close]
    high = [c + 0.15 for c in close]
    low = [c - 0.15 for c in close]
    vol = [1000 + (i % 7) * 11 for i in range(n)]

    df = pl.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )
    idx = pl.arange(0, n, eager=True)
    return df.with_columns(
        [
            pl.lit(0.62).alias("SPS"),
            pl.when(idx % 3 == 0)
            .then(pl.lit("TREND"))
            .when(idx % 3 == 1)
            .then(pl.lit("RANGE"))
            .otherwise(pl.lit("VOLATILE"))
            .alias("Regime_State"),
            pl.lit(1.10).alias("ATR_Ratio"),
        ]
    )


# lightweight schema normalizer so concat never fails
def _ensure_snapshot_schema(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        # construct an empty frame with the full schema
        return pl.DataFrame({c: [] for c in SNAPSHOT_COLS})
    cols = set(df.columns)
    adds: list[pl.Expr] = []
    for c in SNAPSHOT_COLS:
        if c not in cols:
            adds.append(pl.lit(_SNAPSHOT_DEFAULTS[c]).alias(c))
    if adds:
        df = df.with_columns(adds)
    # cast common types so concatenation is stable
    casts = {
        "Tactical_Index": pl.Float64,
        "strategy_score": pl.Float64,
        "entry_ok": pl.Boolean,
        "exit_ok": pl.Boolean,
        "ATR_Ratio": pl.Float64,
        "SPS": pl.Float64,
        "bias": pl.Utf8,
        "risk_band": pl.Utf8,
        "Regime_State": pl.Utf8,
        "Reversal_Stack_Alert": pl.Utf8,
        "symbol": pl.Utf8,
        "timeframe": pl.Utf8,
    }
    for c, t in casts.items():
        if c in df.columns:
            df = df.with_columns(pl.col(c).cast(t, strict=False))
    # final select in canonical order
    return df.select([c for c in SNAPSHOT_COLS if c in df.columns])


# ------------------------------------------------------------
# 🧠 Core meta cycle functions
# ------------------------------------------------------------
def _frames_for(symbol: str, tfs: Iterable[str]) -> Dict[str, pl.DataFrame]:
    """Placeholder for fetch integration — returns dummy frames for now."""
    return {tf: _dummy_ohlcv(240 if "hourly" in tf else 180) for tf in tfs}


def _last_str(df: pl.DataFrame, col: str, default: str = "") -> str:
    if col not in df.columns or df.is_empty():
        return default
    try:
        v = df.select(pl.col(col).cast(pl.Utf8)).tail(1).item()
        return default if v is None else str(v)
    except Exception:
        return default


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _emit_records(
    symbol: str, per_tf: Dict[str, Dict[str, Any]], frames: Dict[str, pl.DataFrame]
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for tf, row in per_tf.items():
        df = frames.get(tf, pl.DataFrame())
        regime_state = _last_str(df, "Regime_State", "NEUTRAL")
        rows.append(
            {
                "timestamp": _utc_now(),
                "symbol": symbol,
                "timeframe": tf,
                "Tactical_Index": round(float(row["strategy_score"]) * 100.0, 1),
                "strategy_score": float(row["strategy_score"]),
                "bias": str(row["bias"]),
                "entry_ok": bool(row["entry_ok"]),
                "exit_ok": bool(row["exit_ok"]),
                "risk_band": str(row["risk_band"]),
                "Regime_State": regime_state,
                "ATR_Ratio": 1.10,
                "SPS": 0.62,
            }
        )
    return rows


def _write_latest_pointer(parquet_path: Path, jsonl_path: Path):
    """Create/update .latest symlinks or copies for dashboards."""
    for src in (parquet_path, jsonl_path):
        dst = src.with_name(
            src.name.replace(".parquet", ".latest.parquet").replace(
                ".jsonl", ".latest.jsonl"
            )
        )
        try:
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            try:
                dst.symlink_to(src)
            except Exception:
                dst.write_bytes(src.read_bytes())
        except Exception:
            pass


def _append_fused_rows(df: pl.DataFrame) -> pl.DataFrame:
    """Append one 'fused' per-symbol row built from TF stack using weights."""
    if df.is_empty() or "symbol" not in df.columns or "timeframe" not in df.columns:
        return _ensure_snapshot_schema(df)

    # 1) Weights per timeframe
    df = df.with_columns(
        pl.when(pl.col("timeframe") == "intraday_15m")
        .then(0.40)
        .when(pl.col("timeframe") == "hourly_1h")
        .then(0.35)
        .when(pl.col("timeframe") == "daily")
        .then(0.25)
        .otherwise(0.0)
        .alias("_w")
    )

    # 2) Ensure essential columns exist/types
    if "strategy_score" not in df.columns:
        df = df.with_columns(pl.lit(0.0).alias("strategy_score"))
    else:
        df = df.with_columns(pl.col("strategy_score").cast(pl.Float64, strict=False))

    for c, v in {
        "SPS": 0.0,
        "Regime_State": "NEUTRAL",
        "ATR_Ratio": 1.0,
        "bias": "neutral",
        "risk_band": "low",
    }.items():
        if c not in df.columns:
            df = df.with_columns(pl.lit(v).alias(c))

    # 3) Weighted aggregation per symbol → fused row
    fused = (
        df.group_by("symbol")
        .agg(
            [
                pl.max("timestamp").alias("timestamp"),
                pl.lit("fused").alias("timeframe"),
                (
                    (pl.col("strategy_score") * pl.col("_w")).sum()
                    / pl.when(pl.col("_w").sum() == 0.0)
                    .then(1.0)
                    .otherwise(pl.col("_w").sum())
                ).alias("strategy_score"),
                pl.first("SPS").alias("SPS"),
                pl.first("Regime_State").alias("Regime_State"),
                pl.first("ATR_Ratio").alias("ATR_Ratio"),
            ]
        )
        .with_columns(
            [
                (pl.col("strategy_score") >= 0.70).alias("entry_ok"),
                (pl.col("strategy_score") <= 0.30).alias("exit_ok"),
                pl.when(pl.col("strategy_score") >= 0.66)
                .then(pl.lit("bullish"))
                .when(pl.col("strategy_score") <= 0.34)
                .then(pl.lit("bearish"))
                .otherwise(pl.lit("neutral"))
                .alias("bias"),
                pl.lit("low").alias("risk_band"),
                (pl.col("strategy_score") * 100).round(1).alias("Tactical_Index"),
            ]
        )
    )

    # 4) Normalize both sides to identical schema/order and concat
    df_norm = _ensure_snapshot_schema(df)
    fused_norm = _ensure_snapshot_schema(fused)

    df_norm = df_norm.select([c for c in SNAPSHOT_COLS if c in df_norm.columns])
    fused_norm = fused_norm.select(
        [c for c in SNAPSHOT_COLS if c in fused_norm.columns]
    )

    combined = pl.concat([df_norm, fused_norm], how="vertical")
    wanted = [c for c in SNAPSHOT_COLS if c in combined.columns]
    return combined.select(wanted)


def run_meta_cycle(
    symbols: Iterable[str],
    tfs: Iterable[str] = ("intraday_15m", "hourly_1h", "daily"),
    *,
    snapshot_parquet: Path | None = None,
    snapshot_jsonl: Path | None = None,
) -> Tuple[Path, Path, pl.DataFrame]:
    snap_dir = SETTINGS.PATHS["SNAPSHOTS"]
    snapshot_parquet = (
        Path(snapshot_parquet or snap_dir / "tactical_snapshot.parquet")
        .expanduser()
        .resolve()
    )
    snapshot_jsonl = (
        Path(snapshot_jsonl or snap_dir / "tactical_snapshot.jsonl")
        .expanduser()
        .resolve()
    )
    snapshot_parquet.parent.mkdir(parents=True, exist_ok=True)
    snapshot_jsonl.parent.mkdir(parents=True, exist_ok=True)

    all_rows: List[Dict[str, Any]] = []

    for symbol in symbols:
        frames = _frames_for(symbol, tfs)
        res = run_strategy(symbol, frames)
        per_tf = res.get("per_tf", {})
        all_rows.extend(_emit_records(symbol, per_tf, frames))

    if not all_rows:
        log.warning("[MetaCycle] No rows produced; skipping writes.")
        return snapshot_parquet, snapshot_jsonl, pl.DataFrame()

    df = pl.DataFrame(all_rows)
    df = _append_fused_rows(df)
    df = df.select([c for c in SNAPSHOT_COLS if c in df.columns])

    io.write_parquet(df, snapshot_parquet)
    for r in all_rows:
        _append_jsonl(snapshot_jsonl, r)
    _cap_jsonl(snapshot_jsonl, 5000)
    _write_latest_pointer(snapshot_parquet, snapshot_jsonl)

    log.info(
        f"[MetaCycle] Wrote snapshot: {len(df)} rows → "
        f"{snapshot_parquet.name} + {snapshot_jsonl.name}"
    )
    return snapshot_parquet, snapshot_jsonl, df


def _discover_symbols(limit: int) -> List[str]:
    """Try to load from universe/instruments if available; else fallback to DEMO."""
    try:
        from queen.helpers.instruments import (
            list_symbols_from_active_universe,
            list_symbols,
        )

        syms = list_symbols_from_active_universe("MONTHLY") or list_symbols("MONTHLY")
        return syms[:limit] if syms else ["DEMO"]
    except Exception:
        return ["DEMO"]


def main():
    parser = argparse.ArgumentParser(
        description="Run Meta Strategy Cycle → tactical snapshot"
    )
    parser.add_argument(
        "--symbols", nargs="*", default=None, help="Symbols (space-separated)"
    )
    parser.add_argument(
        "--limit", type=int, default=SETTINGS.DEFAULTS.get("SYMBOLS_LIMIT", 10)
    )
    parser.add_argument(
        "--tfs", nargs="*", default=["intraday_15m", "hourly_1h", "daily"]
    )
    args = parser.parse_args()

    symbols = args.symbols or _discover_symbols(args.limit)
    if not symbols:
        log.warning("[MetaCycle] No symbols to process; exiting.")
        return

    run_meta_cycle(symbols, args.tfs)


if __name__ == "__main__":
    main()
