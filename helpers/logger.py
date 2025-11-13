#!/usr/bin/env python3
# ============================================================
# queen/helpers/logger.py — v3.1 (Settings-Driven Universal Logger)
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
    Precedence:
      1) env QUEEN_LOG_FILE
      2) settings.LOGGING + settings.PATHS["LOGS"]
      3) fallback queen/data/runtime/logs/core_activity.log
    """
    try:
        import queen.settings.settings as CFG
        log_cfg = getattr(CFG, "LOGGING", {})
        paths = getattr(CFG, "PATHS", {})
    except Exception:
        log_cfg, paths = {}, {}

    env_path = os.getenv("QUEEN_LOG_FILE")
    if env_path:
        p = Path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, log_cfg

    base = Path(paths.get("LOGS") or "queen/data/runtime/logs")
    base.mkdir(parents=True, exist_ok=True)
    fname = (log_cfg.get("FILES", {}) or {}).get("CORE", "core_activity.log")
    return base / fname, log_cfg


log_file, _log_cfg = _resolve_log_cfg()

# Levels/knobs
LEVEL = getattr(logging, _log_cfg.get("LEVEL", "INFO").upper(), logging.INFO)
ROTATE_ENABLED = _log_cfg.get("ROTATE_ENABLED", True)
MAX_SIZE_MB = _log_cfg.get("MAX_SIZE_MB", 25)
BACKUP_COUNT = _log_cfg.get("BACKUP_COUNT", 5)

# Console enablement: explicit env wins; else use settings, but auto-quiet in pytest
_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
_env_console = os.getenv("QUEEN_LOG_CONSOLE")
if _env_console is not None:
    CONSOLE_ENABLED = _env_console != "0"
else:
    CONSOLE_ENABLED = bool(_log_cfg.get("CONSOLE_ENABLED", True)) and not _pytest

# Optional separate console level (defaults to LEVEL)
_CONSOLE_LEVEL_NAME: str | None = _log_cfg.get("CONSOLE_LEVEL") or os.getenv("QUEEN_LOG_CONSOLE_LEVEL")
CONSOLE_LEVEL = getattr(logging, (_CONSOLE_LEVEL_NAME or "").upper(), LEVEL)

ENV = os.getenv("QUEEN_ENV", "dev")


class JSONLFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "pid": os.getpid(),
            "env": ENV,
        }
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


# File handler
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
if CONSOLE_ENABLED:
    _rich_handler = RichHandler(
        console=console,
        markup=True,
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        log_time_format="%H:%M:%S",
    )
    _rich_handler.setLevel(CONSOLE_LEVEL)
    _rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%H:%M:%S]"))

# Logger init
log = logging.getLogger("Queen")
if not getattr(log, "_queen_init_done", False):
    log.setLevel(LEVEL)
    if _rich_handler and not any(isinstance(h, RichHandler) for h in log.handlers):
        log.addHandler(_rich_handler)
    if not any(isinstance(h, (logging.FileHandler, RotatingFileHandler)) for h in log.handlers):
        log.addHandler(_file_handler)
    log.propagate = False
    log._queen_init_done = True  # type: ignore[attr-defined]

    if not _pytest:
        console.print(
            f"[bold green]✅ Logger initialized[/bold green] → {log_file} "
            f"(LEVEL={logging.getLevelName(LEVEL)}, rotate={ROTATE_ENABLED}, console={CONSOLE_ENABLED})"
        )
