# queen/helpers/logger.py

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


@lru_cache(maxsize=1)
def _resolve_log_path() -> Path:
    # 1) explicit override via env
    env_path = os.getenv("QUEEN_LOG_FILE")
    if env_path:
        p = Path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # 2) settings-aware without importing the re-export hub
    try:
        import queen.settings.settings as CFG  # concrete module

        base = getattr(CFG, "PATHS", {}).get("LOGS")
        if base:
            base = Path(base)
            base.mkdir(parents=True, exist_ok=True)
            fname = (
                getattr(CFG, "LOGGING", {})
                .get("FILES", {})
                .get("CORE", "core_activity.log")
            )
            return base / fname
    except Exception:
        pass

    # 3) fallback
    base = Path("queen/data/runtime/logs")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"queen_runtime_{datetime.now():%Y%m%d}.jsonl"


log_file = _resolve_log_path()

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
_rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%H:%M:%S]"))

log = logging.getLogger("Queen")
if not getattr(log, "_queen_init_done", False):
    log.setLevel(logging.INFO)
    log.addHandler(_rich_handler)
    log.addHandler(_file_handler)
    log.propagate = False
    log._queen_init_done = True  # type: ignore[attr-defined]
    console.print(f"[bold green]✅ Logger initialized[/bold green] → {log_file}")
