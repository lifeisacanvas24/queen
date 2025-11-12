#!/usr/bin/env python3
# ============================================================
# queen/helpers/io.py — v3.2 (Universal I/O: JSON/NDJSON/CSV/Parquet + JSONL + safe dirs)
# ============================================================
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import polars as pl

from queen.helpers.logger import log


# ---------- path helpers ----------
def _p(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_dir(path: str | Path) -> Path:
    p = _p(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------- atomic byte write ----------
def _atomic_write_bytes(path: Path, data: bytes) -> None:
    ensure_dir(path)
    with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


# ---------- JSON / NDJSON ----------
def read_json(path: str | Path) -> pl.DataFrame:
    p = _p(path)
    if not p.exists():
        log.warning(f"[IO] JSON not found: {p}")
        return pl.DataFrame()
    try:
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            return pl.DataFrame()
        if p.suffix.lower() in (".jsonl", ".ndjson") or not text.lstrip().startswith("["):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            return pl.DataFrame(rows) if rows else pl.DataFrame()
        return pl.read_json(p)
    except Exception as e:
        log.error(f"[IO] Failed to read JSON {p.name} → {e}")
        return pl.DataFrame()


def write_json(
    data: Any, path: str | Path, *, indent: int = 2, atomic: bool = True
) -> bool:
    p = _p(path)
    try:
        if isinstance(data, pl.DataFrame):
            ensure_dir(p)
            if atomic:
                tmp = p.with_suffix(p.suffix + ".tmp")
                data.write_json(tmp)
                os.replace(tmp, p)
            else:
                data.write_json(p)
        else:
            payload = json.dumps(data, ensure_ascii=False, indent=indent).encode("utf-8")
            if atomic:
                _atomic_write_bytes(p, payload)
            else:
                ensure_dir(p)
                p.write_bytes(payload)
        log.info(f"[IO] JSON written → {p}")
        return True
    except Exception as e:
        log.error(f"[IO] Failed to write JSON {p.name} → {e}")
        return False


##### Parquet #####
def safe_write_parquet(df: pl.DataFrame, path: str | Path) -> bool:
    """Write parquet safely with auto-dir + atomic rename + fallback logging."""
    p = _p(path)
    try:
        ensure_dir(p)
        tmp = p.with_suffix(p.suffix + ".tmp")
        df.write_parquet(tmp, compression="zstd", statistics=True)
        os.replace(tmp, p)
        log.info(f"[IO] Safe parquet written → {p}")
        return True
    except Exception as e:
        log.error(f"[IO] Safe parquet write failed for {p.name} → {e}")
        return False


# ---------- CSV ----------
def read_csv(path: str | Path) -> pl.DataFrame:
    p = _p(path)
    if not p.exists():
        log.warning(f"[IO] CSV not found: {p}")
        return pl.DataFrame()
    try:
        return pl.read_csv(p, ignore_errors=True)
    except Exception as e:
        log.error(f"[IO] Failed to read CSV {p.name} → {e}")
        return pl.DataFrame()


def write_csv(df: pl.DataFrame, path: str | Path, *, atomic: bool = True) -> bool:
    p = _p(path)
    try:
        ensure_dir(p)
        if atomic:
            tmp = p.with_suffix(p.suffix + ".tmp")
            df.write_csv(tmp)
            os.replace(tmp, p)
        else:
            df.write_csv(p)
        log.info(f"[IO] CSV written → {p}")
        return True
    except Exception as e:
        log.error(f"[IO] Failed to write CSV {p.name} → {e}")
        return False


# ---------- Parquet ----------
def read_parquet(path: str | Path) -> pl.DataFrame:
    p = _p(path)
    if not p.exists():
        log.warning(f"[IO] Parquet not found: {p}")
        return pl.DataFrame()
    try:
        return pl.read_parquet(p)
    except Exception as e:
        log.error(f"[IO] Failed to read Parquet {p.name} → {e}")
        return pl.DataFrame()


def write_parquet(df: pl.DataFrame, path: str | Path, *, atomic: bool = True) -> bool:
    p = _p(path)
    try:
        ensure_dir(p)
        if atomic:
            tmp = p.with_suffix(p.suffix + ".tmp")
            df.write_parquet(tmp, compression="zstd", statistics=True)
            os.replace(tmp, p)
        else:
            df.write_parquet(p, compression="zstd", statistics=True)
        log.info(f"[IO] Parquet written → {p}")
        return True
    except Exception as e:
        log.error(f"[IO] Failed to write Parquet {p.name} → {e}")
        return False


# ---------- JSONL (append/tail) ----------
def append_jsonl(path: str | Path, record: dict) -> None:
    p = _p(path)
    ensure_dir(p)
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    with open(p, "ab") as f:
        f.write(line)


def read_jsonl(path: str | Path, limit: int | None = None) -> list[dict]:
    p = _p(path)
    if not p.exists():
        return []
    out: list[dict] = []
    with open(p, "rb") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
            if limit and len(out) >= limit:
                break
    return out


def tail_jsonl(path: str | Path, n: int = 200) -> list[dict]:
    items = read_jsonl(path)
    return items[-n:]


# ---------- convenience ----------
def read_any(path: str | Path) -> pl.DataFrame:
    p = _p(path)
    suf = p.suffix.lower()
    if suf in (".json", ".jsonl", ".ndjson"):
        return read_json(p)
    if suf == ".csv":
        return read_csv(p)
    if suf == ".parquet":
        return read_parquet(p)
    log.warning(f"[IO] Unsupported format for {p}")
    return pl.DataFrame()


def read_text(path: str | Path, default: str = "") -> str:
    try:
        return _p(path).read_text(encoding="utf-8")
    except Exception:
        return default


def write_text(path: str | Path, content: str, *, atomic: bool = True) -> bool:
    p = _p(path)
    try:
        data = content.encode("utf-8")
        if atomic:
            _atomic_write_bytes(p, data)
        else:
            ensure_dir(p)
            p.write_bytes(data)
        return True
    except Exception as e:
        log.error(f"[IO] Text write failed for {p} → {e}")
        return False


# ---------- self-test ----------
if __name__ == "__main__":
    from queen.settings import settings as SETTINGS

    print("🧩 IO smoke test")
    base = SETTINGS.PATHS["TEST_HELPERS"]
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})

    p_csv = base / "io_test.csv"
    p_json = base / "io_test.json"
    p_jsonl = base / "io_test.jsonl"

    write_csv(df, p_csv)
    print(read_csv(p_csv).head(1))

    write_json(df, p_json)
    print(read_json(p_json).shape)

    append_jsonl(p_jsonl, {"ok": 1})
    append_jsonl(p_jsonl, {"ok": 2})
    print(tail_jsonl(p_jsonl, 1))
