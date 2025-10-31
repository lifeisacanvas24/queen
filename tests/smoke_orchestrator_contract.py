from __future__ import annotations

import time

from queen.technicals.signals.tactical.cognitive_orchestrator import run_cognitive_cycle


def test():
    t0 = time.time()
    # should complete quickly (no sleeping/looping)
    run_cognitive_cycle(global_health_dfs=None)
    dt = (time.time() - t0) * 1000
    assert dt < 1500, f"orchestrator took too long for single cycle: {dt:.2f} ms"
    print(f"✅ smoke_orchestrator_contract: single-cycle in {dt:.2f} ms")


if __name__ == "__main__":
    test()
