#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_io.py — v1.0
# ============================================================
from __future__ import annotations

import polars as pl

from queen.helpers import io
from queen.settings.settings import PATHS


def main():
    base = PATHS["TEST_HELPERS"] / "io_smoke"
    base.mkdir(parents=True, exist_ok=True)

    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})

    # CSV
    p_csv = base / "t.csv"
    assert io.write_csv(df, p_csv)
    df_csv = io.read_csv(p_csv)
    assert df_csv.shape == df.shape

    # JSON (array)
    p_json = base / "t.json"
    assert io.write_json(df, p_json)
    df_json = io.read_json(p_json)
    assert df_json.shape == df.shape

    # JSONL append/tail
    p_jsonl = base / "t.jsonl"
    io.append_jsonl(p_jsonl, {"x": 1})
    io.append_jsonl(p_jsonl, {"x": 2})
    tail = io.tail_jsonl(p_jsonl, 1)
    assert tail and tail[-1].get("x") == 2

    # Parquet safe
    p_parquet = base / "t.parquet"
    assert io.write_parquet(df, p_parquet)
    df_pq = io.read_parquet(p_parquet)
    assert df_pq.shape == df.shape

    # read_any dispatch
    assert not io.read_any(base / "unknown.ext").shape[0]  # returns empty DF
    assert io.read_any(p_csv).shape == df.shape
    assert io.read_any(p_json).shape == df.shape
    assert io.read_any(p_parquet).shape == df.shape

    print("✅ smoke_io: passed →", base)

if __name__ == "__main__":
    main()
