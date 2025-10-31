from __future__ import annotations

import asyncio
import contextlib
import os

from queen.technicals.signals.tactical.live_supervisor import (
    HEALTH_FILE,
    run_supervisor,
)


def test():
    async def _run():
        task = asyncio.create_task(run_supervisor())
        await asyncio.sleep(1.0)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # health file may or may not be written in such a short window; don't fail if absent
        if os.path.exists(HEALTH_FILE):
            print("🩺 health snapshot present")
        print("✅ smoke_live_supervisor: launched/cancelled")

    asyncio.run(_run())


if __name__ == "__main__":
    test()
