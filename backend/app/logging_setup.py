"""结构化日志（structlog）+ 文件按天滚动。"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

from .config import settings


def _file_handler(path: Path, level: int) -> logging.Handler:
    h = logging.handlers.TimedRotatingFileHandler(
        path, when="midnight", backupCount=30, encoding="utf-8"
    )
    h.setLevel(level)
    h.setFormatter(logging.Formatter("%(message)s"))
    return h


def setup_logging() -> None:
    settings.ensure_dirs()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    root.addHandler(_file_handler(settings.log_dir / "app.log", level))

    err_h = _file_handler(settings.log_dir / "error.log", logging.WARNING)
    root.addHandler(err_h)

    # 控制台
    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(level)
    stream.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(stream)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
