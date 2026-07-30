from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.config import get_settings
from app.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Analyst-in-the-loop SAR narrative copilot with audit trail. "
            "Week 1: auth, cases, audit. Week 2: RAG + LLM draft generation."
        ),
        lifespan=lifespan,
    )
    app.include_router(api_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
