#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_paths_models.py
# ------------------------------------------------------------
# 🧪 Smoke test — ensure settings.paths.models exists and is writable.
# Confirms model artifacts have a first-class, consistent home.
# ============================================================

from __future__ import annotations

from pathlib import Path

from queen.settings import settings


def test_paths_models():
    models_path: Path = settings.PATHS.get("MODELS")
    assert isinstance(models_path, Path), "MODELS path should be a Path object"
    models_path.mkdir(parents=True, exist_ok=True)
    assert (
        models_path.exists() and models_path.is_dir()
    ), f"MODELS dir missing: {models_path}"

    # try writing a small dummy artifact
    dummy = models_path / "_smoke_model_ok.txt"
    dummy.write_text("models smoke ok")
    assert dummy.exists(), f"Failed to write inside MODELS dir: {dummy}"

    # show result for CI logs or manual runs
    print(f"✅ MODELS path exists and writable → {models_path}")
    print("✅ smoke_paths_models: passed")


if __name__ == "__main__":
    test_paths_models()
