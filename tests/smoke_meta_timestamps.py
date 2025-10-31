# queen/tests/smoke_meta_timestamps.py
from __future__ import annotations

import polars as pl
from queen.technicals.signals.tactical.meta_introspector import (
    _to_datetime_safe,  # type: ignore
)


def test():
    df = pl.DataFrame(
        {
            "timestamp": [
                "2025-10-25T11:02:00Z",
                "2025-10-25T16:32:10+05:30",
                "2025-10-25T11:02:00",
            ]
        }
    )
    out = df.with_columns(_to_datetime_safe(pl.col("timestamp")).alias("timestamp"))
    assert out["timestamp"].dtype.base_type == pl.Datetime, out["timestamp"].dtype
    print("✅ smoke_meta_timestamps: passed")


if __name__ == "__main__":
    test()
