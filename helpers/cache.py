#!/usr/bin/env python3
# ============================================================
# quant/utils/cache.py — Persistent Cache Manager (v7.0 Hybrid-Safe)
# ============================================================
"""Quant-Core v7.0 — Persistent JSON Cache (Hybrid Config Edition)

Purpose:
    ✅ Stores fetch and stream state for resumption
    ✅ JSON storage under config-defined runtime/cache/
    ✅ Thread-safe, rotation-aware, diagnostics-ready
    ✅ Uses config_proxy (no direct quant.config)
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from quant.utils.config_proxy import cfg_bool, cfg_get, cfg_path
from quant.utils.logs import safe_log_init

# ============================================================
# 🧭 Configuration & Logger
# ============================================================
logger = safe_log_init("CacheManager")

# Config-safe path resolution
CACHE_DIR = cfg_path("paths.cache", "./data/runtime/cache")
CACHE_FILE_NAME = cfg_get("files.cache_state", "fetch_state.json")
CACHE_FILE = CACHE_DIR / CACHE_FILE_NAME

# Diagnostics config
DIAG_ENABLED = cfg_bool("diagnostics.enabled", True)
CACHE_CFG = cfg_get("diagnostics.cache", {}) or {}
AUTO_ROTATE = bool(CACHE_CFG.get("auto_rotate", True))
MAX_BACKUPS = int(CACHE_CFG.get("max_snapshots", 3))
PREVIEW_BYTES = int(CACHE_CFG.get("max_preview_bytes", 512))


# ============================================================
# 🧱 CacheManager
# ============================================================
class CacheManager:
    """Thread-safe, config-driven JSON cache for session persistence."""

    def __init__(self, filename: str | None = None) -> None:
        # Resolve final cache path
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            self.cache_file = (self.cache_dir / filename).resolve()
        else:
            self.cache_file = CACHE_FILE

        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}

        self._load()

    # ------------------------------------------------------------
    # 🔒 Internal helpers
    # ------------------------------------------------------------
    def _load(self) -> None:
        """Load existing cache from disk if present."""
        if not self.cache_file.exists():
            if DIAG_ENABLED:
                logger.debug(f"[LOAD] No cache found → {self.cache_file}")
            return
        try:
            with open(self.cache_file, encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info(f"[LOAD] Cache loaded from {self.cache_file.name}")

            if DIAG_ENABLED and len(str(self._data)) > 0:
                preview = str(self._data)[:PREVIEW_BYTES]
                logger.debug(f"[PREVIEW] {preview}")
        except Exception as e:
            logger.warning(f"[LOAD_FAIL] Could not load cache: {e}")
            self._data = {}

    def _save(self) -> None:
        """Atomically persist cache to disk."""
        tmp_path = self.cache_file.with_suffix(".tmp")
        with self._lock:
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                Path(tmp_path).replace(self.cache_file)
                logger.debug(f"[SAVE] Cache persisted ({len(self._data)} keys)")
            except Exception as e:
                logger.error(f"[SAVE_FAIL] {e}")

    # ------------------------------------------------------------
    # 🌐 Public interface
    # ------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """Return cached value for a given key."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set and persist a key-value pair."""
        with self._lock:
            self._data[key] = value
        self._save()

    def delete(self, key: str) -> None:
        """Delete a key from cache."""
        with self._lock:
            if key in self._data:
                del self._data[key]
        self._save()

    def clear(self) -> None:
        """Reset the cache file."""
        with self._lock:
            self._data.clear()
            if self.cache_file.exists():
                self.cache_file.unlink(missing_ok=True)
        logger.info(f"[CLEAR] Cache cleared → {self.cache_file.name}")

    # ------------------------------------------------------------
    # ♻️ Backup Rotation
    # ------------------------------------------------------------
    def _rotate_backups(self, max_backups: int | None = None) -> None:
        """Keep rotated backups of cache file for recovery."""
        try:
            if not AUTO_ROTATE or not self.cache_file.exists():
                return

            max_backups = max_backups or MAX_BACKUPS
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.cache_file.with_name(
                f"{self.cache_file.stem}_{timestamp}.bak"
            )

            shutil.copy2(self.cache_file, backup_file)

            backups = sorted(
                self.cache_dir.glob(f"{self.cache_file.stem}_*.bak"),
                key=lambda f: f.stat().st_mtime,
            )
            while len(backups) > max_backups:
                old = backups.pop(0)
                old.unlink(missing_ok=True)

            logger.info(f"[ROTATE] Backup created → {backup_file.name}")
        except Exception as e:
            logger.warning(f"[ROTATE_FAIL] {e}")

    # ------------------------------------------------------------
    # 💾 Compatibility
    # ------------------------------------------------------------
    def save(self, data: Dict[str, Any]) -> None:
        """Save full cache data (creates backup before writing)."""
        with self._lock:
            self._data.update(data)
        if AUTO_ROTATE:
            self._rotate_backups()
        self._save()

    def load(self) -> Dict[str, Any]:
        """Return the full cache dictionary."""
        self._load()
        return self._data


# ============================================================
# 🧪 CLI Self-Test
# ============================================================
if __name__ == "__main__":
    print("🧩 Quant-Core Cache v7.0 Self-Test")
    c = CacheManager()
    c.set("NETWEB", {"last_ts": "2025-10-10T14:55:00"})
    print("Loaded:", c.get("NETWEB"))
    c.save({"TEST": "Hello"})
    print("Cache contents:", c.load())
    c.clear()
