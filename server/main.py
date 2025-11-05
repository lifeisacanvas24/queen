#!/usr/bin/env python3
# ============================================================
# queen/server/main.py — v0.3 (alerts + cockpit + healthz/version)
# ============================================================
from __future__ import annotations

import platform
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from queen.server.routers import alerts, cockpit
from queen.settings.settings import PATHS
from starlette.requests import Request
from queen.server.routers.routes_monitor import router as monitor_router

# Single source of truth (from settings)
TEMPLATES_DIR: Path = PATHS["TEMPLATES"]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Queen Server",
        version="0.3.0",
        description="Central API for alerts, cockpit scans, and dashboard endpoints",
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Routers ----
    # alerts router expects us to set the prefix here:
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

    # IMPORTANT: cockpit.router already defines prefix="/cockpit" internally.
    # Do NOT add another prefix here, or paths will become /cockpit/cockpit/*.
    app.include_router(cockpit.router)
    app.include_router(monitor_router)
    # ---- Templates ----
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    @app.get("/", include_in_schema=False)
    async def home(request: Request):
        """Simple homepage (useful sanity check for server health)."""
        return templates.TemplateResponse("index.html", {"request": request})

    # ------------------------------------------------------------
    # 🩺 Health & Version Endpoints
    # ------------------------------------------------------------
    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict:
        """Lightweight probe for CI/CD and uptime checks."""
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "server": platform.node(),
            "uptime_sec": round(time.monotonic(), 2),
        }

    @app.get("/version", tags=["meta"])
    async def version() -> dict:
        """Return build metadata for debugging & release tracking."""
        return {
            "app": app.title,
            "version": app.version,
            "description": app.description,
            "templates_dir": str(TEMPLATES_DIR),
        }

    return app


app = create_app()
