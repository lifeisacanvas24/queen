# queen/helpers/portfolio.py
from __future__ import annotations
import json, math
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
from queen.settings.settings import PATHS

_POS_DIR: Path = PATHS["STATIC"] / "positions"
_POS_DIR.mkdir(parents=True, exist_ok=True)

# tiny in-process cache (file contents are small)
__POS_CACHE: Dict[str, Dict[str, dict]] = {}   # key: book name ("all"/"ank"...)

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

def list_books() -> Iterable[str]:
    for f in sorted(_POS_DIR.glob("*.json")):
        yield f.stem

def _load_one(path: Path) -> Dict[str, dict]:
    try:
        data = json.loads(path.read_text())
        # normalize symbols + sanitize numeric values
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

def load_positions(book: str) -> Dict[str, dict]:
    # cache hit
    key = book.lower()
    if key in __POS_CACHE:
        return __POS_CACHE[key]

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
                    agg[sym]["avg_price"] = (a0 * q0 + a * q) / new_q
                    agg[sym]["qty"] = new_q
        __POS_CACHE[key] = agg
        return agg

    path = _POS_DIR / f"{book}.json"
    out = _load_one(path)
    __POS_CACHE[key] = out
    return out

def position_for(symbol: str, book: str = "all") -> Optional[dict]:
    entry = load_positions(book).get(symbol.upper())
    if not entry:
        return None
    q, a = _finite(entry.get("qty", 0)), _finite(entry.get("avg_price", 0))
    return {"qty": q, "avg_price": a} if q > 0 else None

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
