#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_adapter.py — v3.1 (CANONICAL)
# Scraper JSON -> flat row + latest promos + deep tables
# ============================================================
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple, List

from queen.settings.fundamentals_map import FUNDAMENTALS_ADAPTER_COLUMNS

# ----------------- helpers -----------------
def _deep_get(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur

def _deep_get_dot(d: Dict[str, Any], dot_path: str) -> Any:
    return _deep_get(d, dot_path.split(".")) if dot_path else None

def _latest_non_null(v: Any) -> Optional[float]:
    if isinstance(v, dict):
        for x in reversed(list(v.values())):
            if x is None:
                continue
            try:
                return float(x)
            except Exception:
                return None
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        try:
            return float(s)
        except Exception:
            return None
    return None

def _promote_latest_series(out: Dict[str, Any], tbl: Dict[str, Any]) -> None:
    if not isinstance(tbl, dict):
        return
    for metric_key, series in tbl.items():
        latest_val = _latest_non_null(series)
        if latest_val is not None:
            out[f"{metric_key}_latest"] = latest_val

def _extract_latest_period(series: Dict[str, Any]) -> Tuple[str | None, float | None]:
    if not isinstance(series, dict) or not series:
        return (None, None)
    items = list(series.items())
    for period, val in reversed(items):
        if val is not None:
            try:
                return (period, float(val))
            except Exception:
                return (period, None)
    return (items[-1][0], None)

# ----------------- main -----------------
def to_row(m: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    out["Symbol"] = (m.get("symbol") or "").upper().strip()
    out["Sector"] = m.get("sector")

    # baseline scalars from map
    for col, spec in (FUNDAMENTALS_ADAPTER_COLUMNS or {}).items():
        src = spec.get("source")
        if not src:
            continue
        raw_val = _deep_get_dot(m, src)
        out[col] = _latest_non_null(raw_val) if isinstance(raw_val, dict) else raw_val

    # copy all top_ratios internal keys (don’t overwrite)
    top = m.get("top_ratios") or {}
    if isinstance(top, dict):
        for k, v in top.items():
            out.setdefault(k, v)

    # normalize top_ratios roce/roe if scraper used short keys
    if "roce_pct" not in out and "roce" in out:
        out["roce_pct"] = out.get("roce")
    if "roe_pct" not in out and "roe" in out:
        out["roe_pct"] = out.get("roe")

    # deep tables + latest promos
    for tbl_name in ["quarters", "profit_loss", "balance_sheet", "cash_flow", "ratios"]:
        tbl = m.get(tbl_name) or {}
        if isinstance(tbl, dict):
            _promote_latest_series(out, tbl)
        out[f"_{tbl_name}"] = tbl

    # growth flattened
    growth = m.get("growth") or {}
    if isinstance(growth, dict):
        for k, v in growth.items():
            out[k] = v
    out["_growth"] = growth

    # shareholding promotions
    share = m.get("shareholding") or {}
    out["_shareholding"] = share
    if isinstance(share, dict):
        for mode, suffix in [("quarterly", ""), ("yearly", "_yearly")]:
            part = share.get(mode) or {}
            if isinstance(part, dict):
                for key, series in part.items():
                    period, val = _extract_latest_period(series)
                    if val is not None:
                        out[f"{key}_holding{suffix}_latest"] = val
                    if period:
                        out[f"{key}_holding{suffix}_period"] = period

    return out

EXPORTS = {"fundamentals_adapter": {"to_row": to_row}}
