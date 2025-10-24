#!/usr/bin/env python3
# ============================================================
# queen/helpers/schema_adapter.py — v9.1 (Settings-Aware + Introspection)
# ============================================================
"""Queen Schema Adapter — Unified Broker Schema Bridge
------------------------------------------------------
✅ Reads broker schema via settings (single source of truth)
✅ Exposes SCHEMA at module level for consumers (DRY)
✅ Adds get_supported_intervals()/validate helpers for UX/DX
✅ Uses settings-driven log + drift paths
✅ Polars-native builders for candle frames
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import polars as pl
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ============================================================
# ⚙️ Configuration via SETTINGS
# ============================================================
BROKER = SETTINGS.DEFAULTS["BROKER"]
BROKER_CFG = SETTINGS.broker_config(BROKER)

API_SCHEMA_PATH = Path(BROKER_CFG["API_SCHEMA"]).expanduser().resolve()
DRIFT_LOG = SETTINGS.log_file("SCHEMA_DRIFT_LOG")
DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
MARKET_TZ_NAME = SETTINGS.EXCHANGE["MARKET_TIMEZONE"]  # e.g., "Asia/Kolkata"


# ============================================================
# 📜 Load Broker Schema
# ============================================================
def _load_schema() -> dict:
    try:
        schema = json.loads(API_SCHEMA_PATH.read_text())
        log.info(f"[SchemaAdapter] Loaded broker schema: {API_SCHEMA_PATH.name}")
        return schema
    except Exception as e:
        log.error(f"[SchemaAdapter] Failed to load schema → {e}")
        return {}


SCHEMA: Dict[str, Any] = _load_schema()
ERROR_CODES: Dict[str, str] = SCHEMA.get("error_codes", {})
DEFAULT_SCHEMA = ["timestamp", "open", "high", "low", "close", "volume", "oi"]


# ============================================================
# 🔎 Introspection helpers (new)
# ============================================================
def _parse_range_token(tok: str) -> Tuple[int, int]:
    """Parse '1-15' → (1,15) or '1' → (1,1)."""
    tok = str(tok).strip()
    if "-" in tok:
        a, b = tok.split("-", 1)
        return int(a), int(b)
    v = int(tok)
    return v, v


def _collect_intraday_supported() -> Dict[str, Iterable[Tuple[int, int]]]:
    i = SCHEMA.get("intraday_candle_api", {}).get("supported_timelines", {})
    out: Dict[str, Iterable[Tuple[int, int]]] = {}
    for unit, spec in i.items():
        # intraday section uses {"intervals":"1-300"} style
        rng = spec.get("intervals")
        if isinstance(rng, str):
            out[unit] = [_parse_range_token(rng)]
        else:
            out[unit] = []
    return out


def _collect_historical_supported() -> Dict[str, Iterable[Tuple[int, int]]]:
    h = SCHEMA.get("historical_candle_api", {}).get("supported_timelines", {})
    out: Dict[str, Iterable[Tuple[int, int]]] = {}
    for unit, entries in h.items():
        ranges: list[Tuple[int, int]] = []
        if isinstance(entries, list):
            for ent in entries:
                tok = ent.get("intervals")
                if tok:
                    ranges.append(_parse_range_token(tok))
        out[unit] = ranges
    return out


def get_supported_intervals(
    unit: str | None = None, *, intraday: bool | None = None
) -> Dict[str, Iterable[Tuple[int, int]]]:
    """Return supported interval ranges from SCHEMA.
    - unit: 'minutes'|'hours'|'days'|'weeks'|'months' (optional)
    - intraday: True→intraday table, False→historical table, None→merge view

    Returns a dict mapping unit -> list of (min,max) inclusive tuples.
    """
    intr = _collect_intraday_supported()
    hist = _collect_historical_supported()

    if intraday is True:
        table = intr
    elif intraday is False:
        table = hist
    else:
        # merged (prefer hist if both exist for same unit)
        merged = {**intr, **hist}
        table = merged

    if unit:
        u = unit.strip().lower()
        return {u: table.get(u, [])}
    return table


def validate_interval(
    unit: str, interval: int, *, intraday: bool | None = None
) -> bool:
    """Check if interval is supported for the given unit."""
    table = get_supported_intervals(unit, intraday=intraday)
    ranges = list(table.values())[0] if table else []
    for lo, hi in ranges:
        if lo <= interval <= hi:
            return True
    return False


# ============================================================
# 🧩 Helpers
# ============================================================
def _checksum(cols: list[str]) -> str:
    return hashlib.md5(",".join(cols).encode()).hexdigest()


def _normalize(candles: list[list[Any]]) -> list[list[Any]]:
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


# ============================================================
# 🕒 Timestamp Parsing
# ============================================================
def _safe_parse(df: pl.DataFrame, column="timestamp") -> pl.DataFrame:
    try:
        if df.is_empty() or column not in df.columns:
            return df
        if df[column].dtype == pl.Datetime:
            return df
        parsed = (
            pl.Series(df[column])
            .str.strptime(pl.Datetime, strict=False)
            .dt.replace_time_zone(MARKET_TZ_NAME)  # <-- use settings tz name
        )
        return df.with_columns(parsed.alias(column)).sort(column)
    except Exception as e:
        log.warning(f"[SchemaAdapter] Timestamp parse failed → {e}")
        return df


# ============================================================
# 📊 Core Builders
# ============================================================
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
        casts = {
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Int64,
            "oi": pl.Int64,
        }
        for c, t in casts.items():
            if c in df.columns:
                df = df.with_columns(pl.col(c).cast(t, strict=False))
        for meta, val in {"symbol": symbol, "isin": isin}.items():
            if meta not in df.columns:
                df = df.with_columns(pl.lit(val).alias(meta))
        df = _safe_parse(df)
        _detect_drift(df.columns)
        return df.select(DEFAULT_SCHEMA + ["symbol", "isin"])
    except Exception as e:
        log.error(f"[SchemaAdapter] finalize_candle_df failed → {e}")
        return df


# ============================================================
# 🧠 Schema Drift
# ============================================================
_last_hash: str | None = None


def _detect_drift(cols: list[str]):
    global _last_hash
    checksum = _checksum(cols)
    if _last_hash and checksum != _last_hash:
        log.warning(f"[SchemaDrift] Columns changed → {cols}")
        _log_drift(cols)
    _last_hash = checksum


def _log_drift(cols: list[str]):
    record = {"timestamp": datetime.now().isoformat(), "cols": cols}
    try:
        existing = json.loads(DRIFT_LOG.read_text()) if DRIFT_LOG.exists() else []
    except Exception:
        existing = []
    existing.append(record)
    DRIFT_LOG.write_text(json.dumps(existing, indent=2))
    log.info(f"[SchemaDrift] Logged drift → {DRIFT_LOG.name}")


# ============================================================
# ⚠️ Error Handling
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
# 📈 Diagnostics
# ============================================================
def df_summary(df: pl.DataFrame, name="DataFrame") -> dict[str, Any]:
    summary = {
        "name": name,
        "rows": df.height,
        "cols": df.columns,
        "checksum": _checksum(df.columns),
    }
    log.info(f"[Diagnostics] {name} → rows={df.height}, cols={len(df.columns)}")
    return summary


def print_summary(df: pl.DataFrame, title="Schema Summary"):
    table = Table(title=title, expand=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    summary = df_summary(df)
    for k, v in summary.items():
        table.add_row(k, str(v))
    console.print(Panel(table, title="[bold green]📊 Schema Diagnostics[/bold green]"))


# ============================================================
# 🧪 CLI
# ============================================================
def run_cli():
    parser = argparse.ArgumentParser(description="Queen Schema Diagnostics CLI")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--intervals", action="store_true", help="Show supported intervals"
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
        print_summary(df_final, "Test Data Summary")

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
        _detect_drift(df.columns)
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

    else:
        parser.print_help()


if __name__ == "__main__":
    run_cli()
