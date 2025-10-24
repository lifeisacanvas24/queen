import polars as pl


def compute_adx(df: pl.DataFrame) -> dict:
    """Approximate aggregate ADX level if 'adx' column exists per symbol."""
    if "adx" not in df.columns or df.is_empty():
        return {}
    try:
        return {"adx": round(float(df["adx"].mean()), 2)}
    except Exception:
        return {}
