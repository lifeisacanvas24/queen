# queen/tests/smoke_ai_optimizer_paths.py
from __future__ import annotations

from queen.technicals.signals.tactical.ai_optimizer import _weights_out_path


def test():
    w = _weights_out_path()
    w.parent.mkdir(parents=True, exist_ok=True)
    print(f"✅ optimizer weights path OK → {w}")


if __name__ == "__main__":
    test()
