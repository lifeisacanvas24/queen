#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_schema.py — v3.1 (FINAL)
# Pydantic v2 model for processed fundamentals JSON
# ============================================================
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

Number = Union[int, float]
MaybeNumber = Optional[Number]
TimeSeries = Dict[str, MaybeNumber]
TableSeries = Dict[str, TimeSeries]

# Regex for cleaning non-numeric characters
_CLEAN_RE = re.compile(r"[,₹LakhCr%]")

def _clean(x: Any) -> str:
    return str(x).strip() if x is not None else ""

def _coerce_float(x: Any) -> MaybeNumber:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)

    s = _clean(x)
    if not s or s in {"-", "NA", "N/A", "None", "null"}:
        return None

    # Remove commas, currency, etc.
    s = _CLEAN_RE.sub("", s).strip()

    mult = 1.0
    low = s.lower()
    if low.endswith("cr"):
        s = s[:-2].strip()
        mult = 100.0 # Assuming all values are normalized to a consistent unit (e.g., Lakhs or Crores)
    elif low.endswith("lakh"):
        s = s[:-4].strip()
        # mult = 1.0 # If base unit is Lakhs, leave as 1.0

    if s.endswith("%"):
        s = s[:-1].strip()
        mult *= 0.01

    try:
        return float(s) * mult
    except Exception:
        return None


class FundamentalsModel(BaseModel):
    # Pydantic Configuration
    model_config = ConfigDict(extra="allow")

    # Required Metadata
    symbol: str
    sector: Optional[str] = None
    last_updated_date: Optional[str] = None

    # Top Ratios (Flattened, Coerced)
    top_ratios: Dict[str, MaybeNumber] = Field(default_factory=dict)

    # Core Financial Statements (TIME SERIES)
    quarters: TableSeries = Field(default_factory=dict)
    profit_loss: TableSeries = Field(default_factory=dict)
    balance_sheet: TableSeries = Field(default_factory=dict)
    cash_flow: TableSeries = Field(default_factory=dict)

    # Growth & Key Ratios Blocks (Flattened, Coerced)
    growth: Dict[str, MaybeNumber] = Field(default_factory=dict)
    ratios: Dict[str, MaybeNumber] = Field(default_factory=dict)

    # Shareholding (TIME SERIES)
    shareholding: Dict[str, TableSeries] = Field(default_factory=dict)

    # Contextual Data (Text)
    about: Optional[str] = None
    key_points: Optional[List[str]] = Field(default_factory=list)
    pros: Optional[List[str]] = Field(default_factory=list)
    cons: Optional[List[str]] = Field(default_factory=list)

    @field_validator("top_ratios", "ratios", "growth", mode="before")
    @classmethod
    def _norm_flat_metrics(cls, v: Any) -> Dict[str, MaybeNumber]:
        if not isinstance(v, dict):
            return {}
        return {str(k): _coerce_float(val) for k, val in v.items()}

    @field_validator(
        "quarters",
        "profit_loss",
        "balance_sheet",
        "cash_flow",
        mode="before",
    )
    @classmethod
    def _norm_table_series(cls, v: Any) -> TableSeries:
        if not isinstance(v, dict):
            return {}
        out: TableSeries = {}
        for row_key, series in v.items():
            if not isinstance(series, dict):
                continue
            # Ensure series values are coerced
            out[str(row_key)] = {str(p): _coerce_float(x) for p, x in series.items()}
        return out

    # Note: shareholding is complex, it's Dict[category, TableSeries]
    @field_validator("shareholding", mode="before")
    @classmethod
    def _norm_shareholding(cls, v: Any) -> Dict[str, TableSeries]:
        if not isinstance(v, dict):
            return {}

        # Ensure 'quarterly' and 'yearly' keys exist and contain TableSeries
        out: Dict[str, TableSeries] = {}
        for block_key, block_data in v.items():
            if not isinstance(block_data, dict):
                continue

            # Recursively apply _norm_table_series to the inner data (which should be TableSeries)
            out[str(block_key)] = cls._norm_table_series(block_data)

        return out
