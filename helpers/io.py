#!/usr/bin/env python3
# ============================================================
# queen/helpers/io.py — v2.1 (Atomic + Compressed + Polars-first)
# ============================================================
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

import polars as pl
from queen.helpers.logger import log


# -------- paths --------
def _p(path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_parent(path) -> None:
    _p(path).parent.mkdir(parents=True, exist_ok=True)


# -------- atomic write helpers --------
def _atomic_write_bytes(path: Path, data: bytes) -> None:
    ensure_parent(path)
    dirpath = str(path.parent)
    with tempfile.NamedTemporaryFile(dir=dirpath, delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)  # atomic on same filesystem


def write_text_atomic(path: str | Path, text: str) -> None:
    path = _p(path)
    _atomic_write_bytes(path, text.encode("utf-8"))


def write_json_atomic(path: str | Path, obj) -> None:
    write_text_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2))


# -------- JSONL (append-friendly) --------
def append_jsonl(path: str | Path, record: dict) -> None:
    """Append one JSON object per line (creates file if missing)."""
    path = _p(path)
    ensure_parent(path)
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    # Best-effort append (line-level atomicity is OS-dependent)
    with open(path, "ab") as f:
        f.write(line)


def read_jsonl(path: str | Path, limit: Optional[int] = None) -> list[dict]:
    path = _p(path)
    if not path.exists():
        return []
    out: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
            if limit and len(out) >= limit:
                break
    return out


def tail_jsonl(path: str | Path, n: int = 200) -> list[dict]:
    """Cheap tail: reads all if small; acceptable for alert UI."""
    items = read_jsonl(path)
    return items[-n:]


# -------- Parquet --------
_DEFAULT_COMPRESSION = "zstd"  # good ratio/speed
_DEFAULT_STATS = True


def write_parquet(
    path: str | Path,
    df: pl.DataFrame,
    *,
    compression: str = _DEFAULT_COMPRESSION,
    statistics: bool = _DEFAULT_STATS,
) -> None:
    path = _p(path)
    ensure_parent(path)
    with tempfile.NamedTemporaryFile(
        dir=str(path.parent), suffix=".parquet", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.write_parquet(tmp_path, compression=compression, statistics=statistics)
        os.replace(tmp_path, path)
    except Exception as e:
        log.error(f"[IO] write_parquet failed → {e}")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def read_parquet(path: str | Path) -> pl.DataFrame:
    path = _p(path)
    if not path.exists():
        return pl.DataFrame()
    try:
        return pl.read_parquet(path)
    except Exception as e:
        log.error(f"[IO] read_parquet failed → {e}")
        return pl.DataFrame()


# -------- CSV / JSON --------
def write_csv(path: str | Path, df: pl.DataFrame) -> None:
    path = _p(path)
    ensure_parent(path)
    with tempfile.NamedTemporaryFile(
        dir=str(path.parent), suffix=".csv", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.write_csv(tmp_path)
        os.replace(tmp_path, path)
    except Exception as e:
        log.error(f"[IO] write_csv failed → {e}")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def read_csv(path: str | Path) -> pl.DataFrame:
    path = _p(path)
    if not path.exists():
        return pl.DataFrame()
    try:
        return pl.read_csv(path)
    except Exception as e:
        log.error(f"[IO] read_csv failed → {e}")
        return pl.DataFrame()


def write_json(path: str | Path, df: pl.DataFrame) -> None:
    path = _p(path)
    ensure_parent(path)
    with tempfile.NamedTemporaryFile(
        dir=str(path.parent), suffix=".json", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.write_json(tmp_path)
        os.replace(tmp_path, path)
    except Exception as e:
        log.error(f"[IO] write_json failed → {e}")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def read_json(path: str | Path) -> pl.DataFrame:
    """Reads JSON array or NDJSON automatically into Polars."""
    path = _p(path)
    if not path.exists():
        return pl.DataFrame()
    try:
        # Try JSON array first, then NDJSON
        try:
            return pl.read_json(path)
        except Exception:
            return pl.read_ndjson(path)
    except Exception as e:
        log.error(f"[IO] read_json failed → {e}")
        return pl.DataFrame()


# -------- Convenience: read_any --------
def read_any(path: str | Path) -> pl.DataFrame:
    """Read parquet/csv/json/ndjson by extension, else empty DF."""
    path = _p(path)
    suf = path.suffix.lower()
    if suf == ".parquet":
        return read_parquet(path)
    if suf == ".csv":
        return read_csv(path)
    if suf in {".json", ".ndjson"}:
        return read_json(path)
    log.warning(f"[IO] read_any: unsupported extension for {path.name}")
    return pl.DataFrame()
