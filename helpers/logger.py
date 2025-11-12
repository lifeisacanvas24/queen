#!/usr/bin/env python3
# ============================================================
# queen/helpers/logger.py — v3.0 (Settings-Driven Universal Logger)
# ============================================================
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


@lru_cache(maxsize=1)
def _resolve_log_cfg() -> tuple[Path, dict]:
    """Resolve log file path and LOGGING settings once.
    Order of precedence:
        1️⃣ Env var override (QUEEN_LOG_FILE)
        2️⃣ settings.LOGGING + settings.PATHS["LOGS"]
        3️⃣ Fallback to queen/data/runtime/logs
    """
    try:
        import queen.settings.settings as CFG
        log_cfg = getattr(CFG, "LOGGING", {})
        paths = getattr(CFG, "PATHS", {})
    except Exception:
        log_cfg, paths = {}, {}

    # Explicit override wins
    env_path = os.getenv("QUEEN_LOG_FILE")
    if env_path:
        p = Path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, log_cfg

    # settings-based path
    base = paths.get("LOGS") or Path("queen/data/runtime/logs")
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    fname = (log_cfg.get("FILES", {}) or {}).get("CORE", "core_activity.log")
    return base / fname, log_cfg


log_file, _log_cfg = _resolve_log_cfg()

# Read knobs safely with defaults
LEVEL = getattr(logging, _log_cfg.get("LEVEL", "INFO").upper(), logging.INFO)
ROTATE_ENABLED = _log_cfg.get("ROTATE_ENABLED", True)
MAX_SIZE_MB = _log_cfg.get("MAX_SIZE_MB", 25)
BACKUP_COUNT = _log_cfg.get("BACKUP_COUNT", 5)
CONSOLE_ENABLED = _log_cfg.get("CONSOLE_ENABLED", True)
ENV = os.getenv("QUEEN_ENV", "dev")


# -------------------- Handlers --------------------
class JSONLFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "pid": os.getpid(),
            "env": ENV,
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


# File handler (rotating or plain)
if ROTATE_ENABLED:
    _file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_SIZE_MB * 1024 * 1024,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
else:
    _file_handler = logging.FileHandler(log_file, encoding="utf-8")

_file_handler.setFormatter(JSONLFormatter())

# Console handler (Rich)
console = Console()
_rich_handler = None
if CONSOLE_ENABLED and os.getenv("QUEEN_LOG_CONSOLE", "1") != "0":
    _rich_handler = RichHandler(
        console=console,
        markup=True,
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        log_time_format="%H:%M:%S",
    )
    _rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%H:%M:%S]"))


# -------------------- Logger Init --------------------
log = logging.getLogger("Queen")
if not getattr(log, "_queen_init_done", False):
    log.setLevel(LEVEL)
    if _rich_handler and not any(isinstance(h, RichHandler) for h in log.handlers):
        log.addHandler(_rich_handler)
    if not any(isinstance(h, (logging.FileHandler, RotatingFileHandler)) for h in log.handlers):
        log.addHandler(_file_handler)
    log.propagate = False
    log._queen_init_done = True  # type: ignore[attr-defined]

    console.print(
        f"[bold green]✅ Logger initialized[/bold green] → {log_file} "
        f"({LEVEL=}, rotate={ROTATE_ENABLED}, console={CONSOLE_ENABLED})"
    )
