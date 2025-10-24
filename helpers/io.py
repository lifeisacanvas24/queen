#!/usr/bin/env python3
# ============================================================
# queen/helpers/io.py — v2.0 (Atomic + Compressed + Polars-first)
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
    # use atomic append by writing to temp and concatenating when file doesn't exist
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    # Best-effort append (atomicity at line-level is OS-dependent; acceptable for alerts)
    with open(path, "ab") as f:
        f.write(line)


def read_jsonl(path: str | Path, limit: Optional[int] = None) -> list[dict]:
    path = _p(path)
    if not path.exists():
        return []
    out: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
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
    # write to tmp then atomic replace
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


# -------- CSV / JSON (optional minis) --------
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
