#!/usr/bin/env python3
# ============================================================
# queen/server/main.py — v1.1 (Unified entrypoint, de-duped routers)
# ============================================================
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from queen.helpers.market import MARKET_TZ

# Routers (final set)
from queen.server.routers import (
    alerts,  # /alerts/*
    cockpit,  # /cockpit/* and /cockpit/api/*
    instruments,  # /market/instruments/*
    intel,  # /intel/*
    market_state,  # /market/state, /market/gate, ...
    monitor,  # /monitor/*
    pnl,  # /pnl/*
    portfolio,  # /portfolio/*
    services,  # /services/*
)
from queen.settings.settings import PATHS

# Optional analytics router (if present)
try:
    from queen.server.routers import analytics  # /analytics/*
except Exception:
    analytics = None

TEMPLATES_DIR: Path = PATHS["TEMPLATES"]

# ------------------------------------------------------------
# Application Factory
# ------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(title="Queen Server", version="1.0.0")

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(cockpit.router)            # pages + JSON for cockpit/*
    app.include_router(alerts.router)
    app.include_router(market_state.router)       # /market/*
    app.include_router(instruments.router) # /market/instruments/*
    app.include_router(monitor.router)            # /monitor/*
    app.include_router(intel.router)
    app.include_router(pnl.router)
    app.include_router(portfolio.router)
    app.include_router(services.router)
    if analytics:
        app.include_router(analytics.router)

    # --- Templates ---
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    return app


def render(request, tpl_name: str, ctx: dict | None = None):
    """Optional helper if some routers still call render()."""
    ctx = ctx or {}
    ctx.setdefault("now", datetime.now(MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S IST"))
    return request.app.state.templates.TemplateResponse(
        tpl_name, {"request": request, **ctx}
    )

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
app = create_app()
