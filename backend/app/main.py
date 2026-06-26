"""FastAPI 入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import admin, chat, export, providers, session
from .config import settings
from .db.session import init_db
from .logging_setup import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="话图 T2G",
        version="0.3.0",
        description="用自然语言画数学图形（K12 平面几何）",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(session.router)
    app.include_router(chat.router)
    app.include_router(export.router)
    app.include_router(providers.router)
    app.include_router(admin.router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": app.version}

    return app


app = create_app()
