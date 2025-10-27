# queen/server/routers/alerts.py
import asyncio
import json
from typing import AsyncIterator, List

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from queen.helpers import io  # <-- use your helper
from queen.settings import settings as SETTINGS

router = APIRouter()

ALERTS_PATH = SETTINGS.PATHS["EXPORTS"] / "alerts"
ALERTS_FILE = ALERTS_PATH / "alerts.jsonl"
ALERTS_PATH.mkdir(parents=True, exist_ok=True)


@router.post("/ingest")
async def ingest_alert(payload: dict):
    """Append one alert as a JSON line using io.append_jsonl (atomic-ish)."""
    try:
        io.append_jsonl(ALERTS_FILE, payload)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def _tail_lines(path, n: int) -> List[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            lines = data.splitlines()[-n:]
            return [ln.decode("utf-8", errors="ignore") for ln in lines]
    except FileNotFoundError:
        return []
    except Exception:
        try:
            return open(path, encoding="utf-8").read().splitlines()[-n:]
        except Exception:
            return []


@router.get("/recent")
async def recent(n: int = 50):
    ALERTS_FILE.touch(exist_ok=True)
    lines = ALERTS_FILE.read_text(encoding="utf-8").splitlines()[-max(1, n) :]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return {"items": out}


async def _tail_jsonl(replay: int = 0) -> AsyncIterator[str]:
    """SSE: optionally replay last N lines, then tail -f alerts.jsonl with keep-alive."""
    ALERTS_FILE.touch(exist_ok=True)

    # Announce readiness
    yield "event: ready\ndata: {}\n\n"

    # Optional replay of last N lines
    if replay and replay > 0:
        for ln in _tail_lines(ALERTS_FILE, replay):
            ln = ln.strip()
            if ln:
                yield f"data: {ln}\n\n"

    # Follow new lines
    last_heartbeat = 0.0
    with ALERTS_FILE.open("r", encoding="utf-8") as f:
        f.seek(0, 2)  # go to end
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.5)
                last_heartbeat += 0.5
                if last_heartbeat >= 10.0:
                    yield ": keep-alive\n\n"
                    last_heartbeat = 0.0
                continue
            last_heartbeat = 0.0
            yield f"data: {line.strip()}\n\n"


@router.get("/stream")
async def stream_alerts(request: Request, replay: int = Query(0, ge=0, le=500)):
    # e.g., /alerts/stream?replay=25
    return StreamingResponse(_tail_jsonl(replay=replay), media_type="text/event-stream")
