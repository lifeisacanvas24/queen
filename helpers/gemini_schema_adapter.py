# ============================================================
# queen/helpers/schema_adapter.py — v10.0 (Refactored)
# ============================================================
"""Queen Schema Adapter — Unified Broker Schema Bridge (Refactored)
------------------------------------------------------
✅ Imports shared helpers from schema_helper.py (DRY)
✅ Focuses on candle-specific logic (e.g., interval parsing, candle normalization)
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS
# --- Import shared utilities ---
from queen.helpers.schema_helper import (
    _safe_select, _safe_parse, _checksum, _detect_drift,
    df_summary, print_summary
)

console = Console()

# ============================================================
# ⚙️ Configuration via SETTINGS
# ============================================================
BROKER = SETTINGS.DEFAULTS["BROKER"]
BROKER_CFG = SETTINGS.broker_config(BROKER)

API_SCHEMA_PATH = Path(BROKER_CFG["api_schema"]).expanduser().resolve()
DRIFT_LOG = SETTINGS.log_file("SCHEMA")
DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# 📜 Load Broker Schema
# ============================================================
def _load_schema() -> dict:
    try:
        schema = json.loads(API_SCHEMA_PATH.read_text(encoding="utf-8"))
        log.info(f"[SchemaAdapter] Loaded broker schema: {API_SCHEMA_PATH.name}")
        return schema
    except Exception as e:
        log.error(f"[SchemaAdapter] Failed to load schema → {e}")
        return {}


SCHEMA: dict[str, Any] = _load_schema()
ERROR_CODES: dict[str, str] = SCHEMA.get("error_codes", {})
# Candle-specific schema definition
DEFAULT_SCHEMA = ["timestamp", "open", "high", "low", "close", "volume", "oi"]


# ============================================================
# 🔎 Candle Introspection helpers (Specific to this adapter)
# ============================================================
def _parse_range_token(tok: str) -> tuple[int, int]:
    # ... (Implementation is identical to original, but kept here
    # because it is configuration-specific based on historical/intraday_candle_api) ...
    tok = str(tok).strip()
    if "-" in tok:
        a, b = tok.split("-", 1)
        return int(a), int(b)
    v = int(tok)
    return v, v


def _collect_intraday_supported() -> dict[str, Iterable[tuple[int, int]]]:
    intr = SCHEMA.get("intraday_candle_api", {}).get("supported_timelines", {})
    out: dict[str, Iterable[tuple[int, int]]] = {}
    for unit, spec in intr.items():
        # Handle the structure where 'intervals' can be a string token or a list of dicts
        rng = spec.get("intervals") if isinstance(spec, dict) else None
        if isinstance(spec, list): # Historical API uses a list of dicts
             ranges = []
             for ent in spec:
                 tok = ent.get("intervals")
                 if tok:
                     ranges.append(_parse_range_token(tok))
             out[unit] = ranges
        elif rng:
            out[unit] = [_parse_range_token(rng)]
    return out


def _collect_historical_supported() -> dict[str, Iterable[tuple[int, int]]]:
    # ... (Implementation is identical to original, but kept here) ...
    hist = SCHEMA.get("historical_candle_api", {}).get("supported_timelines", {})
    out: dict[str, Iterable[tuple[int, int]]] = {}
    for unit, entries in hist.items():
        ranges: list[tuple[int, int]] = []
        if isinstance(entries, list):
            for ent in entries:
                tok = ent.get("intervals")
                if tok:
                    ranges.append(_parse_range_token(tok))
        out[unit] = ranges
    return out


def get_supported_intervals(
    unit: str | None = None, *, intraday: bool | None = None
) -> dict[str, Iterable[tuple[int, int]]]:
    # ... (Implementation is identical to original, but kept here) ...
    intr = _collect_intraday_supported()
    hist = _collect_historical_supported()

    if intraday is True:
        table = intr
    elif intraday is False:
        table = hist
    else:
        table = {**intr, **hist}

    if unit:
        u = unit.strip().lower()
        return {u: table.get(u, [])}
    return table


def validate_interval(
    unit: str, interval: int, *, intraday: bool | None = None
) -> bool:
    # ... (Implementation is identical to original, but kept here) ...
    table = get_supported_intervals(unit, intraday=intraday)
    ranges = list(table.values())[0] if table else []
    return any(lo <= interval <= hi for lo, hi in ranges)


# ============================================================
# 📊 Core Candle Builders (Specific to this adapter)
# ============================================================
def _normalize(candles: list[list[Any]]) -> list[list[Any]]:
    """Ensures all candle lists have exactly the DEFAULT_SCHEMA length."""
    expected = len(DEFAULT_SCHEMA)
    normalized = []
    for row in candles:
        if not isinstance(row, list):
            continue
        if len(row) < expected:
            row += [0] * (expected - len(row))
        elif len(row) > expected:
            row = row[:expected]
        normalized.append(row)
    return normalized


def to_candle_df(candles: list[list[Any]], symbol: str) -> pl.DataFrame:
    if not candles:
        return pl.DataFrame()
    try:
        candles = _normalize(candles)
        df = pl.DataFrame(candles, schema=DEFAULT_SCHEMA, orient="row")
        df = df.with_columns(pl.lit(symbol).alias("symbol"))
        return _safe_parse(df)
    except Exception as e:
        log.error(f"[SchemaAdapter] to_candle_df failed → {e}")
        return pl.DataFrame()


def finalize_candle_df(df: pl.DataFrame, symbol: str, isin: str) -> pl.DataFrame:
    if df.is_empty():
        return pl.DataFrame(schema=DEFAULT_SCHEMA + ["symbol", "isin"])
    try:
        # Casts and metadata assignment specific to candle data
        casts = {
            "open": pl.Float64, "high": pl.Float64, "low": pl.Float64,
            "close": pl.Float64, "volume": pl.Int64, "oi": pl.Int64,
        }
        for c, t in casts.items():
            if c in df.columns:
                df = df.with_columns(pl.col(c).cast(t, strict=False))
        for meta, val in {"symbol": symbol, "isin": isin}.items():
            if meta not in df.columns:
                df = df.with_columns(pl.lit(val).alias(meta))

        df = _safe_parse(df)
        _detect_drift(df.columns, DRIFT_LOG) # Uses imported helper
        return _safe_select(df, DEFAULT_SCHEMA + ["symbol", "isin"]) # Uses imported helper
    except Exception as e:
        log.error(f"[SchemaAdapter] finalize_candle_df failed → {e}")
        return df


# ============================================================
# ⚠️ Error Handling (Specific to this adapter)
# ============================================================
class UpstoxAPIError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or ERROR_CODES.get(code, "Unknown error")
        super().__init__(f"[{code}] {self.message}")


def handle_api_error(code: str):
    if code in ERROR_CODES:
        raise UpstoxAPIError(code)
    log.error(f"[SchemaAdapter] Unmapped error code: {code}")
    raise UpstoxAPIError(code, "Unmapped error code.")


# ============================================================
# 🧪 CLI
# ============================================================
def run_cli():
    # ... (CLI implementation, using imported print_summary) ...
    parser = argparse.ArgumentParser(description="Queen Schema Diagnostics CLI")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--intervals", action="store_true", help="Show supported intervals"
    )
    parser.add_argument(
        "--drift-sim", type=int, default=0, help="Append N simulated drift entries"
    )
    args = parser.parse_args()

    sample = [
        ["2025-01-01T09:15:00", 100, 110, 90, 105, 5000, 12],
        ["2025-01-01T09:20:00", 106, 108, 104, 107, 3200, 9],
    ]

    if args.test:
        console.rule("[bold green]🧪 Running Schema Self-Test")
        df = to_candle_df(sample, "UPSTOX_TEST")
        df_final = finalize_candle_df(df, "UPSTOX_TEST", "ISIN999")
        print_summary(df_final, console, "Test Data Summary") # Use imported print_summary
    elif args.summary:
        console.rule("[bold cyan]📄 Current Schema Summary")
        table = Table(show_header=True, title="Broker Field Mapping")
        table.add_column("Section", style="bold magenta")
        table.add_column("Fields", style="white")
        for section, fields in SCHEMA.get("field_mapping", {}).items():
            table.add_row(section, ", ".join(fields))
        console.print(Panel(table, title="[bold green]📘 Broker Schema[/bold green]"))
    elif args.validate:
        console.rule("[bold yellow]🔍 Schema Validation")
        df = pl.DataFrame({"timestamp": [1], "open": [10], "close": [20]})
        _detect_drift(df.columns, DRIFT_LOG) # Use imported _detect_drift
        console.print(Panel("✅ Validation completed.", style="green bold"))
    elif args.intervals:
        console.rule("[bold blue]⏱ Supported Intervals")
        intr = get_supported_intervals(intraday=True)
        hist = get_supported_intervals(intraday=False)
        table = Table(show_header=True, title="Supported Intervals")
        table.add_column("Scope", style="bold magenta")
        table.add_column("Unit", style="cyan")
        table.add_column("Ranges", style="white")
        for scope, dat in (("intraday", intr), ("historical", hist)):
            for unit, ranges in dat.items():
                pretty = ", ".join(
                    [f"{a}-{b}" if a != b else f"{a}" for a, b in ranges]
                )
                table.add_row(scope, unit, pretty or "—")
        console.print(
            Panel(table, title="[bold green]🕒 Broker Capability[/bold green]")
        )
    elif args.drift_sim > 0:
        console.rule("[bold yellow]🧪 Simulating drift entries")
        for i in range(args.drift_sim):
            from queen.helpers.schema_helper import _log_drift # Local import for simulation
            _log_drift([f"sim_col_{i}", "open", "close"], DRIFT_LOG)
        console.print(
            Panel(f"Inserted {args.drift_sim} drift entries.", style="yellow")
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    run_cli()
