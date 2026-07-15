"""FastAPI 入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import admin, audit_log, auth, chat, chat_stream, export, payment, providers, session, webhooks
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
    app.include_router(chat_stream.router)
    app.include_router(export.router)
    app.include_router(providers.router)
    app.include_router(admin.router)
    # V2-F.1：用户管理 + 审计
    app.include_router(auth.router)
    app.include_router(audit_log.router)
    # V2-F.2：付费 + webhook
    app.include_router(payment.router)
    app.include_router(webhooks.router)

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": app.version,
            "debug_ui": settings.debug_ui,
        }

    return app


app = create_app()
