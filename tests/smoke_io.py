#!/usr/bin/env python3
# queen/tests/smoke_io.py
from __future__ import annotations

from pathlib import Path

import polars as pl
from queen.helpers import io
from queen.settings.settings import PATHS


def test():
    base = (
        PATHS["TEST_HELPERS"]
        if "TEST_HELPERS" in PATHS
        else PATHS["RUNTIME"] / "test_helpers"
    )
    base = Path(base).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)

    df = pl.DataFrame({"a": [1, 2, 3], "b": [10.0, 11.0, 12.0]})

    p_parquet = base / "io_demo.parquet"
    p_csv = base / "io_demo.csv"
    p_json = base / "io_demo.json"
    p_jsonl = base / "io_demo.jsonl"

    # parquet
    io.write_parquet(p_parquet, df)
    df_pq = io.read_parquet(p_parquet)
    assert df_pq.height == df.height and df_pq.columns == df.columns

    # csv
    io.write_csv(p_csv, df)
    df_csv = io.read_csv(p_csv)
    assert df_csv.height == df.height

    # json (array)
    io.write_json(p_json, df)
    df_js = io.read_json(p_json)
    assert df_js.height == df.height

    # jsonl (append 2 records, then tail)
    io.append_jsonl(p_jsonl, {"x": 1})
    io.append_jsonl(p_jsonl, {"x": 2})
    last = io.tail_jsonl(p_jsonl, 1)
    assert last and last[-1].get("x") == 2

    # read_any router sanity
    assert io.read_any(p_parquet).height == df.height
    assert io.read_any(p_csv).height == df.height
    assert io.read_any(p_json).height == df.height

    print("✅ smoke_io: passed")


if __name__ == "__main__":
    test()
