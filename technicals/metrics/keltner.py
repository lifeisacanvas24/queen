# queen/technicals/metrics/keltner.py
import polars as pl


def compute_keltner(df: pl.DataFrame) -> dict:
    """Approximate average Keltner Channel width if columns exist."""
    if not {"keltner_upper", "keltner_lower"}.issubset(df.columns):
        return {}
    try:
        width = (df["keltner_upper"] - df["keltner_lower"]).mean()
        return {"keltner_bandwidth": round(float(width), 3)}
    except Exception:
        return {}
