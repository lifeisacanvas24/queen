#!/usr/bin/env python3
# ============================================================
# queen/helpers/portfolio.py — v2.0
# ------------------------------------------------------------
# Positions loader with:
#   • static/positions/*_positions.json layout
#   • mtime-aware in-process cache (per book + "all")
#   • simple P&L helpers
# ============================================================

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from queen.settings.settings import PATHS

_POS_DIR: Path = PATHS["STATIC"] / "positions"
_POS_DIR.mkdir(parents=True, exist_ok=True)

# tiny in-process cache (file contents are small)
#   __POS_CACHE[key]        → symbol → {qty, avg_price}
#   __POS_MTIME[key]        → float mtime fingerprint
__POS_CACHE: Dict[str, Dict[str, dict]] = {}
__POS_MTIME: Dict[str, float] = {}


def _finite(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    return x if math.isfinite(x) else 0.0


def _sanitize_entry(sym: str, pos: dict) -> dict:
    return {
        "qty": _finite(pos.get("qty", 0)),
        "avg_price": _finite(pos.get("avg_price", 0)),
    }


def _book_path_candidates(book: str) -> list[Path]:
    """Return candidate json filenames for a given book.

    Examples:
        book='ank'  → ['ank.json', 'ank_positions.json']
        book='ank_positions' → ['ank_positions.json']
    """
    slug = (book or "").strip().lower()
    cands = []
    if slug:
        cands.append(_POS_DIR / f"{slug}.json")
        if not slug.endswith("_positions"):
            cands.append(_POS_DIR / f"{slug}_positions.json")
    return cands


def list_books() -> Iterable[str]:
    """Yield logical book names (without '_positions' suffix)."""
    seen: set[str] = set()
    # prefer *_positions.json naming
    for f in sorted(_POS_DIR.glob("*_positions.json")):
        name = f.stem.replace("_positions", "")
        if name not in seen:
            seen.add(name)
            yield name
    # also allow plain .json files (if any)
    for f in sorted(_POS_DIR.glob("*.json")):
        stem = f.stem
        if stem.endswith("_positions"):
            stem = stem.replace("_positions", "")
        if stem not in seen:
            seen.add(stem)
            yield stem


def _load_one(path: Path) -> Dict[str, dict]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        out: Dict[str, dict] = {}
        for sym, pos in (data or {}).items():
            if not isinstance(pos, dict):
                continue
            s = _sanitize_entry(sym, pos)
            if s["qty"] > 0 and s["avg_price"] > 0:
                out[sym.upper()] = s
        return out
    except Exception:
        return {}


def _current_mtime_for_book_all() -> float:
    """Aggregate mtime fingerprint for book='all'."""
    mtimes = [f.stat().st_mtime for f in _POS_DIR.glob("*.json")]
    return max(mtimes) if mtimes else 0.0


def _current_mtime_for_book(book: str) -> float:
    """Mtime fingerprint for a specific book (0.0 if file missing)."""
    for p in _book_path_candidates(book):
        if p.exists():
            return p.stat().st_mtime
    return 0.0


def load_positions(book: str) -> Dict[str, dict]:
    """Load positions for a book.

    Layout:
        queen/data/static/positions/*_positions.json

    Args:
        book:  "all" → merge all jsons
               "<name>" → first matching <name>.json or <name>_positions.json

    Returns:
        dict[symbol] = {"qty": float, "avg_price": float}
    """
    key = (book or "all").strip().lower()

    # --- mtime fingerprint for cache validation ---
    if key == "all":
        mtime = _current_mtime_for_book_all()
    else:
        mtime = _current_mtime_for_book(key)

    # cache hit with same mtime
    if key in __POS_CACHE and __POS_MTIME.get(key, -1.0) == mtime:
        return __POS_CACHE[key]

    # --- rebuild cache for this key ---
    if key == "all":
        agg: Dict[str, dict] = {}
        for f in _POS_DIR.glob("*.json"):
            data = _load_one(f)
            for sym, pos in data.items():
                q, a = _finite(pos.get("qty", 0)), _finite(pos.get("avg_price", 0))
                if q <= 0 or a <= 0:
                    continue
                if sym not in agg:
                    agg[sym] = {"qty": q, "avg_price": a}
                else:
                    q0, a0 = agg[sym]["qty"], agg[sym]["avg_price"]
                    new_q = q0 + q
                    if new_q <= 0:
                        continue
                    agg[sym]["avg_price"] = (a0 * q0 + a * q) / new_q
                    agg[sym]["qty"] = new_q
        __POS_CACHE[key] = agg
        __POS_MTIME[key] = mtime
        return agg

    # specific book
    data: Dict[str, dict] = {}
    for p in _book_path_candidates(key):
        if p.exists():
            data = _load_one(p)
            break

    __POS_CACHE[key] = data
    __POS_MTIME[key] = mtime
    return data


def position_for(symbol: str, book: str = "all") -> Optional[dict]:
    entry = load_positions(book).get((symbol or "").strip().upper())
    if not entry:
        return None
    q, a = _finite(entry.get("qty", 0)), _finite(entry.get("avg_price", 0))
    return {"qty": q, "avg_price": a} if q > 0 and a > 0 else None


def compute_pnl(cmp_price: float, pos: Optional[dict]) -> Optional[Tuple[float, float]]:
    if not pos:
        return None
    qty = _finite(pos.get("qty", 0))
    avg = _finite(pos.get("avg_price", 0))
    if qty <= 0 or avg <= 0:
        return None
    pnl_abs = (cmp_price - avg) * qty
    pnl_pct = ((cmp_price / avg) - 1.0) * 100.0
    return (pnl_abs, pnl_pct)


def clear_positions_cache() -> None:
    __POS_CACHE.clear()
    __POS_MTIME.clear()
