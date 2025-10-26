#!/usr/bin/env python3
# ============================================================
# queen/helpers/logger.py — Unified Logging System (v9.1)
# ============================================================
"""Queen Unified Logger (Rich + JSONL, settings-driven)

✅ Colorized console + structured JSONL output
✅ All log paths & files driven by queen.settings.settings.LOGGING
✅ DRY — one source of truth for file destinations
✅ Safe fallback for offline/standalone mode
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None

# ------------------------------------------------------------
# 🧭 Setup Directories (settings-aware)
# ------------------------------------------------------------
if SETTINGS:
    base_log_dir = SETTINGS.PATHS["LOGS"]
    base_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = SETTINGS.log_file("CORE")
else:
    base_log_dir = Path("queen/data/runtime/logs")
    base_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = base_log_dir / f"queen_runtime_{datetime.now():%Y%m%d}.jsonl"

# ------------------------------------------------------------
# 🎨 Rich + JSONL Handlers
# ------------------------------------------------------------
console = Console()
_rich_handler = RichHandler(
    console=console,
    markup=True,
    rich_tracebacks=True,
    show_time=True,
    show_path=False,
    log_time_format="%H:%M:%S",
)


class JSONLFormatter(logging.Formatter):
    """Emit JSON lines for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


_file_handler = logging.FileHandler(log_file, encoding="utf-8")
_file_handler.setFormatter(JSONLFormatter())

_rich_formatter = logging.Formatter("%(message)s", datefmt="[%H:%M:%S]")
_rich_handler.setFormatter(_rich_formatter)

# ------------------------------------------------------------
# ⚙️ Logger Initialization (idempotent)
# ------------------------------------------------------------
log = logging.getLogger("Queen")
if not getattr(log, "_queen_init_done", False):
    log.setLevel(logging.INFO)
    log.addHandler(_rich_handler)
    log.addHandler(_file_handler)
    log.propagate = False
    log._queen_init_done = True  # type: ignore[attr-defined]
    console.print(f"[bold green]✅ Logger initialized[/bold green] → {log_file}")

# ------------------------------------------------------------
# 🧪 Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    log.info("Logger ready — Rich + JSONL active.")
    log.warning("Simulated warning for diagnostics.")
    log.error("Simulated error message.")
    log.info(f"Logs written to: {log_file}")
