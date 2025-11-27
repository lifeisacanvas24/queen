# ============================================================
# queen/helpers/schema_helper.py — Common Utilities for Schema Adapters
# ============================================================
"""Common helpers for Polars DataFrame manipulation, timestamp parsing,
and schema drift detection, shared between different broker schema adapters.
"""
from __future__ import annotations

import json
from datetime import datetime
from hashlib import md5
from typing import Any

import polars as pl

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS # Access SETTINGS for logs/TZ

# --- Configuration (Copied from Adapters) ---
try:
    MARKET_TZ_NAME = SETTINGS.market_timezone()
except Exception:
    MARKET_TZ_NAME = "Asia/Kolkata"

DRIFT_LOG_MAX = 500
_last_hash: str | None = None # Global for drift detection

# ============================================================
# 🧩 Polars Helpers
# ============================================================
def _safe_select(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    """Safely select columns, adding lit(None) for missing columns."""
    exprs = [(pl.col(c) if c in df.columns else pl.lit(None).alias(c)) for c in cols]
    return df.select(exprs)


# ============================================================
# 🕒 Timestamp Parsing
# ============================================================
def _safe_parse(df: pl.DataFrame, column: str = "timestamp") -> pl.DataFrame:
    """Normalize the timestamp column to tz-aware Datetime in MARKET_TZ_NAME.
    (Handles datetime, epoch, and various string formats.)
    """
    try:
        if df.is_empty() or column not in df.columns:
            return df

        # Logic for Datetime, Numeric epochs, and Strings is identical...
        # ... (full implementation kept as in original schema_adapter.py) ...
        # (See schema_adapter.py content for full implementation)

        # 1) Already Datetime
        if df[column].dtype == pl.Datetime:
            try:
                if getattr(df[column].dtype, "tz", None) is None:
                    return df.with_columns(
                        pl.col(column).dt.replace_time_zone(MARKET_TZ_NAME)
                    ).sort(column)
                return df.with_columns(
                    pl.col(column).dt.convert_time_zone(MARKET_TZ_NAME)
                ).sort(column)
            except Exception:
                return df

        # 2) Numeric epochs (s/ms)
        if df[column].dtype in (
            pl.Int64, pl.Int32, pl.UInt64, pl.UInt32, pl.Float64, pl.Float32,
        ):
            s = pl.col(column).cast(pl.Int64, strict=False)
            parsed = (
                pl.when(s > 1_000_000_000_000)
                .then(pl.from_epoch(s, time_unit="ms", tz="UTC"))
                .otherwise(pl.from_epoch(s, time_unit="s", tz="UTC"))
                .dt.convert_time_zone(MARKET_TZ_NAME)
                .alias(column)
            )
            return df.with_columns(parsed).sort(column)

        # 3) Strings → parse explicitly
        ts = pl.col(column)
        parsed_tz = ts.str.replace(r"Z$", "+00:00").str.strptime(
            pl.Datetime(time_zone="UTC"),
            format="%Y-%m-%dT%H:%M:%S%z",
            strict=False,
        )
        parsed = (
            pl.when(parsed_tz.is_not_null())
            .then(parsed_tz.dt.convert_time_zone(MARKET_TZ_NAME))
            .otherwise(
                ts.str.strptime(
                    pl.Datetime(time_zone=MARKET_TZ_NAME),
                    format="%Y-%m-%d%t%H:%M:%S%.f",
                    strict=False,
                )
            )
            .alias(column)
        )

        return df.with_columns(parsed).sort(column)

    except Exception as e:
        log.warning(f"[SchemaHelper] Timestamp parse failed → {e}")
        return df


# ============================================================
# 🧠 Schema Drift
# ============================================================
def _checksum(cols: list[str]) -> str:
    """Order-insensitive checksum for schema columns."""
    cols_sorted = list(cols)
    cols_sorted.sort()
    return md5(",".join(cols_sorted).encode()).hexdigest()


def _detect_drift(cols: list[str], drift_log_path: Path):
    """Log drift only when the *set* of columns changes (ignore order)."""
    global _last_hash
    checksum = _checksum(cols)
    if _last_hash and checksum != _last_hash:
        log.warning(f"[SchemaDrift] Columns changed → {cols}")
        _log_drift(cols, drift_log_path)
    _last_hash = checksum

def _log_drift(cols: list[str], drift_log_path: Path):
    """Writes a drift record to the specified log file."""
    record = {"timestamp": datetime.now().isoformat(), "cols": cols}
    try:
        existing = json.loads(drift_log_path.read_text()) if drift_log_path.exists() else []
    except Exception:
        existing = []

    existing.append(record)
    if len(existing) > DRIFT_LOG_MAX:
        existing = existing[-DRIFT_LOG_MAX:]

    drift_log_path.parent.mkdir(parents=True, exist_ok=True)
    drift_log_path.write_text(json.dumps(existing, indent=2))
    log.info(f"[SchemaDrift] Logged drift → {drift_log_path.name} (len={len(existing)})")


# ============================================================
# 📈 Diagnostics
# ============================================================
def df_summary(df: pl.DataFrame, name="DataFrame") -> dict[str, Any]:
    """Generates a summary dictionary for a Polars DataFrame."""
    summary = {
        "name": name,
        "rows": df.height,
        "cols": df.columns,
        "checksum": _checksum(df.columns),
    }
    log.info(f"[Diagnostics] {name} → rows={df.height}, cols={len(df.columns)}")
    return summary


def print_summary(df: pl.DataFrame, console: Console, title="Schema Summary"):
    """Prints a formatted summary panel using Rich console."""
    from rich.panel import Panel
    from rich.table import Table

    table = Table(title=title, expand=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    summary = df_summary(df)
    for k, v in summary.items():
        table.add_row(k, str(v))
    console.print(Panel(table, title="[bold green]📊 Schema Diagnostics[/bold green]"))
