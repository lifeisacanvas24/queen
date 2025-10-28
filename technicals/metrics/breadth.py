# queen/technicals/metrics/breadth.py
import polars as pl


def compute_breadth(df: pl.DataFrame) -> dict:
    """Compute advance-decline ratio."""
    if not {"open", "close"}.issubset(df.columns):
        return {}
    adv = (df["close"] > df["open"]).sum()
    dec = (df["close"] < df["open"]).sum()
    total = adv + dec
    ratio = adv / total if total else 0
    return {"breadth_ratio": round(float(ratio), 3)}
