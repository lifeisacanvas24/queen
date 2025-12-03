#!/usr/bin/env python3
# ============================================================
# queen/fetchers/options_chain.py — v1.0
# Upstox options chain fetcher (schema-driven, Polars-only)
# ============================================================
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
import polars as pl

from queen.helpers.logger import log
from queen.helpers.options_schema import get_options_schema


class OptionsAPIError(Exception):
    """Raised when Upstox options API returns a non-success status."""


@dataclass
class OptionsChainRequest:
    instrument_key: str        # e.g. "NSE_EQ|GROWW"
    expiry_date: Optional[str] = None  # "YYYY-MM-DD" or None → nearest expiry
    side: Optional[str] = None         # "call" | "put" | None (both)


def _auth_token() -> str:
    token = os.getenv("UPSTOX_TOKEN") or os.getenv("UPSTOX_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "[OptionsChain] UPSTOX_TOKEN / UPSTOX_ACCESS_TOKEN not set in env"
        )
    return token


def _build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _handle_error(
    resp: httpx.Response,
    *,
    info: str = "",
) -> None:
    schema = get_options_schema("upstox")
    msg = schema.explain_http_error(resp.status_code)
    detail = resp.text.strip()
    if detail:
        msg = f"{msg} | body={detail[:512]}"
    if info:
        msg = f"{info} → {msg}"
    raise OptionsAPIError(msg)


def fetch_option_chain(
    req: OptionsChainRequest,
    *,
    timeout: float = 10.0,
) -> pl.DataFrame:
    """Fetch PUT/CALL option chain for a given underlying instrument_key.

    Returns:
        Polars DataFrame with one row per option contract.
        Columns are directly from Upstox JSON (no renaming yet).

    Note:
        - This is a pure data fetch; scoring / signals sit on top.
        - F&O gating (only call for F&O symbols) will be handled upstream.

    """
    schema = get_options_schema("upstox")
    ep = schema.option_chain_def()

    method = (ep.get("http_method") or "GET").upper()
    path = ep.get("url_pattern") or "/option/chain"
    url = f"{schema.base_url}{path}"

    params: Dict[str, Any] = {}

    qdef = ep.get("query_params") or {}
    # We align with schema field names; no hardcoding paths.
    # Common Upstox params for option chain:
    #   - instrument_key (underlying)
    #   - expiry_date (YYYY-MM-DD)
    #   - side ("call"/"put") – optional
    if "instrument_key" in qdef:
        params[qdef["instrument_key"].get("name", "instrument_key")] = req.instrument_key
    else:
        params["instrument_key"] = req.instrument_key

    if req.expiry_date:
        exp_key = (
            qdef.get("expiry_date", {}).get("name")
            if "expiry_date" in qdef
            else "expiry_date"
        )
        params[exp_key] = req.expiry_date

    if req.side:
        side_key = (
            qdef.get("side", {}).get("name")
            if "side" in qdef
            else "side"
        )
        params[side_key] = req.side

    token = _auth_token()
    headers = _build_headers(token)

    log.info(
        f"[OptionsChain] Fetching chain for {req.instrument_key} "
        f"expiry={req.expiry_date or 'nearest'} side={req.side or 'both'}"
    )

    with httpx.Client(timeout=timeout) as client:
        resp = client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
        )

    if resp.status_code != 200:
        _handle_error(resp, info=f"Option chain {req.instrument_key}")

    payload = resp.json()
    data = payload.get("data")

    if not data:
        log.warning(
            f"[OptionsChain] Empty chain for {req.instrument_key} "
            f"(expiry={req.expiry_date}, side={req.side})"
        )
        return pl.DataFrame([])

    # Upstox usually returns a list of contracts objects in `data`
    if isinstance(data, dict):
        # Some variants may wrap list under `option_chain` etc.
        for key in ("option_chain", "contracts", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break

    if not isinstance(data, list):
        raise OptionsAPIError(
            f"[OptionsChain] Unexpected data format for {req.instrument_key}: "
            f"type={type(data)!r}"
        )

    df = pl.DataFrame(data)
    log.info(
        f"[OptionsChain] Received {df.height} contracts for {req.instrument_key}"
    )
    return df


# ------------------------------------------------------------
# CLI usage for quick manual tests:
#   python -m queen.fetchers.options_chain "NSE_EQ|GROWW" 2024-12-26 call
#   python -m queen.fetchers.options_chain "NSE_EQ|GROWW"
# ------------------------------------------------------------
def _cli() -> None:
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python -m queen.fetchers.options_chain "
            "INSTRUMENT_KEY [EXPIRY_YYYY-MM-DD] [side]",
            file=sys.stderr,
        )
        raise SystemExit(1)

    instrument_key = sys.argv[1]
    expiry = sys.argv[2] if len(sys.argv) >= 3 else None
    side = sys.argv[3] if len(sys.argv) >= 4 else None

    req = OptionsChainRequest(
        instrument_key=instrument_key,
        expiry_date=expiry,
        side=side,
    )
    df = fetch_option_chain(req)
    if df.is_empty():
        print("No contracts returned.")
    else:
        # small preview
        print(df.head(10))


if __name__ == "__main__":
    _cli()
