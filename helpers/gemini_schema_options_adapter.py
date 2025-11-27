# ============================================================
# queen/helpers/schema_options_adapter.py — v10.0 (Refactored)
# ============================================================
"""Queen Schema Options Adapter — Unified Options Schema Bridge (Refactored)
-------------------------------------------------------------
✅ Imports shared helpers from schema_helper.py (DRY)
✅ Focuses on options-specific logic (e.g., contract building, error mapping)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
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
    _safe_parse, _detect_drift,
    df_summary, print_summary
)

console = Console()

# ============================================================
# ⚙️ Configuration via SETTINGS
# ============================================================
BROKER = SETTINGS.DEFAULTS["BROKER"]
BROKER_CFG = SETTINGS.broker_config(BROKER)

OPTIONS_SCHEMA_KEY = "api_options_schema"
API_SCHEMA_PATH = Path(BROKER_CFG.get(OPTIONS_SCHEMA_KEY, "api_upstox_options.json")).expanduser().resolve()
DRIFT_LOG = SETTINGS.log_file("OPTIONS_SCHEMA")
DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# 📜 Load Broker Schema
# ============================================================
def _load_schema() -> dict:
    try:
        schema = json.loads(API_SCHEMA_PATH.read_text(encoding="utf-8"))
        log.info(f"[OptionsSchemaAdapter] Loaded broker options schema: {API_SCHEMA_PATH.name}")
        return schema
    except Exception as e:
        log.error(f"[OptionsSchemaAdapter] Failed to load schema → {e}")
        return {}


SCHEMA: dict[str, Any] = _load_schema()
ERROR_CODES: dict[str, str] = SCHEMA.get("error_codes_http_status", {})


# ============================================================
# 📊 Core Builders (Specific to this adapter)
# ============================================================
def to_contract_df(data: list[dict[str, Any]], key_col: str) -> pl.DataFrame:
    """Builds a Polars DataFrame from a list of option contract dictionaries."""
    if not data:
        return pl.DataFrame()
    try:
        df = pl.DataFrame(data)

        if "timestamp" not in df.columns:
            df = df.with_columns(pl.lit(datetime.now()).alias("timestamp"))

        if key_col in df.columns:
            df = df.with_columns(pl.col(key_col).cast(pl.String, strict=False).alias(key_col))
            df = df.sort(key_col)

        df = _safe_parse(df) # Use imported helper
        _detect_drift(df.columns, DRIFT_LOG) # Use imported helper
        return df
    except Exception as e:
        log.error(f"[OptionsSchemaAdapter] to_contract_df failed → {e}")
        return pl.DataFrame()


# ============================================================
# ⚠️ Error Handling (Specific to this adapter)
# ============================================================
class UpstoxOptionsAPIError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or ERROR_CODES.get(code, "Unknown error")
        super().__init__(f"[{code}] {self.message}")


def handle_api_error(code: str):
    if code in ERROR_CODES:
        message = ERROR_CODES.get(code, "Unmapped error code.")
        raise UpstoxOptionsAPIError(code, message)
    log.error(f"[OptionsSchemaAdapter] Unmapped error code: {code}")
    raise UpstoxOptionsAPIError(code, "Unmapped error code.")


# ============================================================
# 🧪 CLI
# ============================================================
def run_cli():
    # ... (CLI implementation, using imported print_summary) ...
    parser = argparse.ArgumentParser(description="Queen Options Schema Diagnostics CLI")
    parser.add_argument("--summary", action="store_true", help="Show the loaded API schema summary.")
    parser.add_argument("--errors", action="store_true", help="Show mapped error codes.")
    parser.add_argument("--test", action="store_true", help="Run a simple DataFrame test.")
    parser.add_argument(
        "--drift-sim", type=int, default=0, help="Append N simulated drift entries"
    )
    args = parser.parse_args()

    if args.test:
        console.rule("[bold green]🧪 Running Schema Self-Test")
        sample_data = [
            {"strike_price": 18000.0, "instrument_key": "NSE_FO|NIFTY25JAN18000CE", "exchange": "NSE_FO"},
            {"strike_price": 18100.0, "instrument_key": "NSE_FO|NIFTY25JAN18100CE", "exchange": "NSE_FO"},
        ]
        df = to_contract_df(sample_data, "instrument_key")
        print_summary(df, console, "Test Contract Data Summary") # Use imported print_summary
    elif args.summary:
        console.rule("[bold cyan]📄 Current Options Schema Summary")
        table = Table(show_header=True, title="Options API Endpoints")
        table.add_column("Endpoint", style="bold magenta")
        table.add_column("Summary", style="white")
        table.add_column("URL Pattern", style="yellow")

        for name, data in SCHEMA.get("endpoints", {}).items():
            table.add_row(name, data.get("summary", "N/A"), data.get("url_pattern", "N/A"))
        console.print(Panel(table, title="[bold green]📘 Options API Endpoints[/bold green]"))

        table2 = Table(show_header=True, title="Common Schema Fields")
        table2.add_column("Schema", style="bold magenta")
        table2.add_column("Fields", style="white")
        for section, fields in SCHEMA.get("common_schemas", {}).items():
            table2.add_row(section, ", ".join(fields))
        console.print(Panel(table2, title="[bold blue]🧩 Data Schemas[/bold blue]"))
    elif args.errors:
        console.rule("[bold red]❌ Mapped Error Codes")
        table = Table(show_header=True, title="Error Codes")
        table.add_column("Code", style="bold red")
        table.add_column("Description", style="white")
        for code, desc in ERROR_CODES.items():
            table.add_row(code, desc)
        console.print(Panel(table, title="[bold red]⚠️ Error Mapping[/bold red]"))
    elif args.drift_sim > 0:
        console.rule("[bold yellow]🧪 Simulating drift entries")
        for i in range(args.drift_sim):
            from queen.helpers.schema_helper import _log_drift # Local import for simulation
            _log_drift([f"sim_col_{i}", "strike_price", "instrument_key"], DRIFT_LOG)
        console.print(
            Panel(f"Inserted {args.drift_sim} drift entries.", style="yellow")
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    run_cli()
