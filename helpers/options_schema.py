#!/usr/bin/env python3
# ============================================================
# queen/helpers/options_schema.py — v1.0
# Schema adapter for Upstox OPTIONS endpoints (chain, contracts)
# ============================================================
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS


@dataclass(frozen=True)
class OptionsSchema:
    """Lightweight view over the broker's options schema JSON."""

    broker: str
    base_url: str
    endpoints: Dict[str, Any]
    error_codes: Dict[str, Any]

    @classmethod
    def load(cls, broker: str = "upstox") -> OptionsSchema:
        cfg = SETTINGS.broker_config(broker)
        path_str = (
            cfg.get("api_schema_options")
            or cfg.get("options_api_schema")
        )
        if not path_str:
            raise RuntimeError(
                f"[OptionsSchema] No options schema configured for broker={broker}"
            )

        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(
                f"[OptionsSchema] Options schema file not found at {path}"
            )

        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        base_url = (raw.get("base_url") or "").rstrip("/")
        endpoints = raw.get("endpoints") or {}
        error_codes = raw.get("error_codes_http_status") or {}

        log.info(f"[OptionsSchema] Loaded options schema: {path.name}")
        return cls(
            broker=broker,
            base_url=base_url,
            endpoints=endpoints,
            error_codes=error_codes,
        )

    # -----------------------------
    # Endpoint helpers
    # -----------------------------
    def option_chain_def(self) -> Dict[str, Any]:
        """Return the endpoint definition for PUT/CALL option chain."""
        ep = self.endpoints.get("get_put_call_option_chain") or {}
        if not ep:
            raise KeyError(
                "[OptionsSchema] Missing 'get_put_call_option_chain' in schema"
            )
        return ep

    def option_contracts_def(self) -> Dict[str, Any]:
        """Return endpoint definition for listing option contracts."""
        ep = self.endpoints.get("get_option_contracts") or {}
        if not ep:
            raise KeyError(
                "[OptionsSchema] Missing 'get_option_contracts' in schema"
            )
        return ep

    # -----------------------------
    # Error helpers
    # -----------------------------
    def explain_http_error(self, status_code: int) -> str:
        """Best-effort human description for a non-200 HTTP response."""
        entry = self.error_codes.get(str(status_code)) or self.error_codes.get(
            status_code
        )
        if not entry:
            return f"HTTP {status_code} (no mapped options error)."
        # schema may store an object or list; we normalize
        if isinstance(entry, dict):
            return entry.get("description") or f"HTTP {status_code}"
        if isinstance(entry, list):
            msg = ", ".join(
                e.get("description", e.get("code", ""))
                for e in entry
                if isinstance(e, dict)
            ).strip()
            return msg or f"HTTP {status_code}"
        return str(entry)


# -----------------------------
# Singleton accessor
# -----------------------------
_SCHEMA_CACHE: Optional[OptionsSchema] = None


def get_options_schema(broker: str = "upstox") -> OptionsSchema:
    """Return cached OptionsSchema, loading from disk on first use."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None or _SCHEMA_CACHE.broker != broker:
        _SCHEMA_CACHE = OptionsSchema.load(broker)
    return _SCHEMA_CACHE
