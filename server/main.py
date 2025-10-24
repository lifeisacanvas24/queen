from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from queen.settings import settings as SETTINGS
from starlette.requests import Request

from .routers import alerts


def create_app() -> FastAPI:
    app = FastAPI(title="Queen Server", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

    # Static+templates (Bulma via CDN; templates for quick UI)
    templates = Jinja2Templates(
        directory=str(SETTINGS.PATHS["ROOT"].parent / "server" / "templates")
    )
    app.state.templates = templates

    @app.get("/")
    async def home(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    return app


app = create_app()
