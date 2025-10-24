import polars as pl


def compute_sector_heatmap(df: pl.DataFrame) -> dict:
    """Stub example — returns sector averages if 'sector' column exists."""
    if "sector" not in df.columns or "close" not in df.columns:
        return {}
    try:
        grouped = df.groupby("sector").agg(pl.col("close").mean().alias("avg_close"))
        return {
            "sector_heatmap": {r["sector"]: round(float(r["avg_close"]), 2) for r in grouped.to_dicts()}
        }
    except Exception:
        return {}
