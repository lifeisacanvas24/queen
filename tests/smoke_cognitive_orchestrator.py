from __future__ import annotations

from queen.technicals.signals.tactical.cognitive_orchestrator import run_cognitive_cycle


def test():
    run_cognitive_cycle(df_live=None, do_train=False)
    print("✅ smoke_cognitive_orchestrator: passed")


if __name__ == "__main__":
    test()
