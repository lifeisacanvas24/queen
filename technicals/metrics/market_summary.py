import polars as pl


def compute_market_summary(df: pl.DataFrame) -> dict:
    if df.is_empty():
        return {}
    try:
        return {
            "avg_close": float(df["close"].mean()) if "close" in df.columns else 0.0,
            "total_volume": float(df["volume"].sum()) if "volume" in df.columns else 0.0
        }
    except Exception:
        return {}
