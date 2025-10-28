#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_helpers.py — IO & pl_compat sanity checks
# ============================================================
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from queen.helpers import (
    _s2np,
    append_jsonl,
    ensure_float_series,
    read_any,
    read_csv,
    read_json,
    read_parquet,
    safe_concat,
    tail_jsonl,
    write_csv,
    write_json,
    write_parquet,
)

TMP = Path("queen/data/runtime/_test_helpers")
TMP.mkdir(parents=True, exist_ok=True)


def _make_df(n: int = 25) -> pl.DataFrame:
    ts = list(range(n))
    base = [100.0 + i for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": base,
            "high": [x + 1.0 for x in base],
            "low": [x - 1.0 for x in base],
            "close": base,
            "volume": [1000] * n,
        }
    )


def test_parquet_roundtrip():
    df = _make_df(33)
    p = TMP / "x.parquet"
    write_parquet(p, df)
    out = read_parquet(p)
    assert out.height == 33
    assert out.columns == df.columns


def test_csv_roundtrip():
    df = _make_df(17)
    p = TMP / "x.csv"
    write_csv(p, df)
    out = read_csv(p)
    assert out.height == 17
    assert set(out.columns) == set(df.columns)


def test_json_roundtrip_array():
    df = _make_df(11)
    p = TMP / "x.json"
    write_json(p, df)
    out = read_json(p)
    assert out.height == 11


def test_read_any_switch():
    df = _make_df(9)
    p = TMP / "y.parquet"
    write_parquet(p, df)
    out = read_any(p)
    assert out.height == 9


def test_jsonl_tail_append():
    p = TMP / "log.jsonl"
    if p.exists():
        p.unlink()
    for i in range(5):
        append_jsonl(p, {"i": i})
    tail = tail_jsonl(p, n=3)
    assert len(tail) == 3
    assert tail[-1]["i"] == 4


def test_s2np_and_float_series():
    df = _make_df(5)
    arr = _s2np(df["close"])
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (5,)
    s = ensure_float_series(df["close"])
    assert s.dtype.is_float()


def test_safe_concat():
    a = _make_df(3)
    b = _make_df(0)
    c = _make_df(2)
    out = safe_concat([a, None, b, c])
    assert out.height == 5


if __name__ == "__main__":
    test_parquet_roundtrip()
    test_csv_roundtrip()
    test_json_roundtrip_array()
    test_read_any_switch()
    test_jsonl_tail_append()
    test_s2np_and_float_series()
    test_safe_concat()
    print("✅ smoke_helpers: all checks passed")
