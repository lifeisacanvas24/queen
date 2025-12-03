# queen/technicals/volume_strength.py
from __future__ import annotations

import polars as pl


def compute_volume_strength(df: pl.DataFrame) -> str:
    """Returns: "strong", "medium", "weak"
    Based on last bar volume vs last 20-bar average.
    Expects a 'volume' column.
    """
    if df.height < 20 or "volume" not in df.columns:
        return "weak"

    recent = df.tail(1).get_column("volume").item()
    avg20 = df.tail(20).get_column("volume").mean()

    if avg20 is None or avg20 <= 0:
        return "weak"

    if recent >= 1.8 * avg20:
        return "strong"
    if recent >= 1.2 * avg20:
        return "medium"
    return "weak"
