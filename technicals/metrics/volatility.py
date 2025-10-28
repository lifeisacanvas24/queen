# queen/technicals/metrics/volatility.py
import polars as pl


def compute_volatility(df: pl.DataFrame) -> dict:
    """Simple volatility proxy."""
    if not {"high", "low", "close"}.issubset(df.columns):
        return {}
    vol = ((df["high"] - df["low"]) / df["close"]).mean()
    return {"volatility_index": round(float(vol), 3)}
