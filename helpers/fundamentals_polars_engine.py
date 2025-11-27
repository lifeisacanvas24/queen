#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_polars_engine.py — v3.2 (SAFE AUTO-SCHEMA)
# ------------------------------------------------------------
# Mode A: SAFE AUTO-SCHEMA
#   • Builds DF from adapter rows without crashing on mixed types
#   • If any non-numeric string appears in a column, dtype becomes Utf8
#   • Deep tables (_quarters, _ratios, etc.) always Object
#   • Numeric candidates are cast w/ strict=False (bad strings -> null)
#
# Back-compat exports:
#   load_all()  ✅  (devcheck/smoke expect this)
#   load_one_processed()
#   to_polars_row()
#   build_df_from_rows()
#   build_df_from_all_processed()
# ============================================================
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import polars as pl

from queen.helpers.fundamentals_adapter import to_row
from queen.helpers.fundamentals_schema import FundamentalsModel
from queen.settings.fundamentals_map import (
    FUNDAMENTALS_ADAPTER_COLUMNS,
    FUNDAMENTALS_METRIC_COLUMNS,
)
from queen.helpers.logger import log


# ------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------
def _read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"[FUND-POLAR] JSON read failed: {p.name}: {e}")
        return None


def _validate_or_fallback(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Try Pydantic validation/coercion.
    Fallback to raw dict if Screener drifts.
    """
    try:
        model = FundamentalsModel.model_validate(raw)
        return model.model_dump()
    except Exception as e:
        log.warning(f"[FUND-POLAR] Validation fallback for {source}: {e}")
        return raw


def _is_numeric_like_str(s: str) -> bool:
    """
    Accepts numeric-like strings:
      "12.3", "-4", "0.08", "1,234"
    Rejects:
      "TTM", "Sep 2024", "NA"
    """
    if s is None:
        return False
    t = s.strip().replace(",", "")
    if t in {"", "-", "NA", "N/A", "None", "null"}:
        return False
    try:
        float(t)
        return True
    except Exception:
        return False


def _infer_dtype_for_col(values: List[Any], col: str) -> pl.DataType:
    """
    Mode A SAFE inference:
      - deep cols => Object
      - any dict/list => Object
      - any real string (non numeric-like) => Utf8
      - else => Float64
    """
    if col.startswith("_"):
        return pl.Object

    saw_text = False
    saw_object = False
    saw_numeric = False

    for v in values:
        if v is None:
            continue

        if isinstance(v, (dict, list)):
            saw_object = True
            break

        if isinstance(v, str):
            if _is_numeric_like_str(v):
                saw_numeric = True
            else:
                saw_text = True
                break

        elif isinstance(v, (int, float)):
            saw_numeric = True

        else:
            # unknown python object -> safest object
            saw_object = True
            break

    if saw_object:
        return pl.Object
    if saw_text:
        return pl.Utf8
    if saw_numeric:
        return pl.Float64

    # all nulls -> keep float (neutral)
    return pl.Float64


def _build_safe_schema(rows: List[Dict[str, Any]]) -> Dict[str, pl.DataType]:
    """
    Scan ALL rows to infer a safe dtype per column.
    """
    all_cols: Set[str] = set()
    for r in rows:
        all_cols.update(r.keys())

    schema: Dict[str, pl.DataType] = {}
    for c in sorted(all_cols):
        col_vals = [r.get(c) for r in rows]
        schema[c] = _infer_dtype_for_col(col_vals, c)

    # enforce identity cols as Utf8
    for idc in ("Symbol", "symbol"):
        if idc in schema:
            schema[idc] = pl.Utf8
    for sc in ("Sector", "sector"):
        if sc in schema:
            schema[sc] = pl.Utf8

    return schema


def _ensure_symbol_sector(df: pl.DataFrame) -> pl.DataFrame:
    if "symbol" in df.columns and "Symbol" not in df.columns:
        df = df.rename({"symbol": "Symbol"})
    if "sector" in df.columns and "Sector" not in df.columns:
        df = df.rename({"sector": "Sector"})
    return df


def _numeric_candidates(df: pl.DataFrame) -> List[str]:
    """
    Columns that SHOULD be numeric (cast safely).
    We include:
      - baseline metric cols
      - adapter baseline cols
      - *_latest, *_holding_latest
      - CAGR keys
      - slope/accel/CV keys
      - z-score columns
    """
    base = set(FUNDAMENTALS_METRIC_COLUMNS or [])
    base.update(FUNDAMENTALS_ADAPTER_COLUMNS.keys())

    out: List[str] = []
    for c in df.columns:
        if c in {"Symbol", "Sector"} or c.startswith("_"):
            continue
        if (
            c in base
            or c.endswith("_latest")
            or c.endswith("_holding_latest")
            or "_cagr_" in c
            or c.endswith("_Slope")
            or c.endswith("_Accel")
            or c.endswith("_CV")
            or c.endswith("_z_sector")
            or c.endswith("_z_global")
        ):
            out.append(c)

    return out


def _cast_numeric_candidates(df: pl.DataFrame) -> pl.DataFrame:
    """
    Cast numeric candidates to Float64 safely.
    If a col had stray text (like "TTM"), it becomes null for that row.
    """
    cands = _numeric_candidates(df)
    if not cands:
        return df

    exprs = [
        pl.col(c).cast(pl.Float64, strict=False).alias(c)
        for c in cands
        if c in df.columns
    ]
    return df.with_columns(exprs) if exprs else df


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
def load_one_processed(processed_dir: Union[str, Path], symbol: str) -> Optional[Dict[str, Any]]:
    processed_dir = Path(processed_dir)
    p = processed_dir / f"{symbol.upper()}.json"
    if not p.exists():
        return None

    raw = _read_json(p)
    if not raw:
        return None

    return _validate_or_fallback(raw, p.name)


def to_polars_row(symbol_fund_json: Dict[str, Any]) -> Dict[str, Any]:
    safe = _validate_or_fallback(symbol_fund_json, "inline")
    return to_row(safe)


def build_df_from_rows(rows: Iterable[Dict[str, Any]]) -> pl.DataFrame:
    rows = list(rows)
    if not rows:
        return pl.DataFrame()

    # 🔥 SAFE AUTO-SCHEMA
    schema = _build_safe_schema(rows)

    df = pl.DataFrame(rows, schema=schema, strict=False)
    df = _ensure_symbol_sector(df)

    # safe numeric cast pass
    df = _cast_numeric_candidates(df)

    return df


def build_df_from_all_processed(processed_dir: Union[str, Path]) -> pl.DataFrame:
    processed_dir = Path(processed_dir)
    files = sorted(processed_dir.glob("*.json"))

    if not files:
        log.warning(f"[FUND-POLAR] No processed JSONs in {processed_dir}")
        return pl.DataFrame()

    rows: List[Dict[str, Any]] = []
    log.info(f"[FUND-POLAR] Processing {len(files)} fundamental files...")

    for p in files:
        raw = _read_json(p)
        if not raw:
            continue

        safe = _validate_or_fallback(raw, p.name)

        try:
            row = to_row(safe)
            if row.get("Symbol") or row.get("symbol"):
                rows.append(row)
            else:
                log.warning(f"[FUND-POLAR] Missing Symbol in {p.name}, skipped")
        except Exception as e:
            log.error(f"[FUND-POLAR] Adapter failed for {p.name}: {e}")

    if not rows:
        log.warning("[FUND-POLAR] No rows after adapter")
        return pl.DataFrame()

    df = build_df_from_rows(rows)
    log.info(
        f"[FUND-POLAR] Final DF built with {df.height} symbols and "
        f"{len(df.columns)} columns."
    )
    return df


# ------------------------------------------------------------
# Back-compat alias (devcheck/smoke expect load_all)
# ------------------------------------------------------------
def load_all(processed_dir: Union[str, Path]) -> pl.DataFrame:
    return build_df_from_all_processed(processed_dir)


EXPORTS = {
    "fundamentals_polars_engine": {
        "load_all": load_all,  # ✅ back-compat
        "load_one_processed": load_one_processed,
        "to_polars_row": to_polars_row,
        "build_df_from_rows": build_df_from_rows,
        "build_df_from_all_processed": build_df_from_all_processed,
    }
}
