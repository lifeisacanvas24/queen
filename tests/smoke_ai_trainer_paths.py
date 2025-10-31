# queen/tests/smoke_ai_trainer_paths.py
from __future__ import annotations
from pathlib import Path
from queen.technicals.signals.tactical.ai_trainer import _event_log_path, _model_path
from quant import config


def test():
    logs = _event_log_path()
    models = _model_path()
    assert logs.parent.exists(), logs
    models.parent.mkdir(parents=True, exist_ok=True)
    (models.parent / ".touch_ok").write_text("ok")
    print(f"✅ trainer paths OK → logs={logs} models={models}")


if __name__ == "__main__":
    test()
