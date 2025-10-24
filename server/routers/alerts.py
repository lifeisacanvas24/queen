import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from queen.settings import settings as SETTINGS

router = APIRouter()

ALERTS_PATH = SETTINGS.PATHS["EXPORTS"] / "alerts"
ALERTS_FILE = ALERTS_PATH / "alerts.jsonl"
ALERTS_PATH.mkdir(parents=True, exist_ok=True)


@router.post("/ingest")
async def ingest_alert(payload: dict):
    try:
        with ALERTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def _tail_jsonl() -> AsyncIterator[str]:
    """Simple tail -f for alerts.jsonl as SSE stream."""
    ALERTS_FILE.touch(exist_ok=True)
    with ALERTS_FILE.open("r", encoding="utf-8") as f:
        f.seek(0, 2)  # go to end
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.5)
                continue
            yield f"data: {line.strip()}\n\n"


@router.get("/stream")
async def stream_alerts(request: Request):
    # Server-Sent Events
    return StreamingResponse(_tail_jsonl(), media_type="text/event-stream")
