"""轻量 schema 迁移：检测缺失列并自动 ALTER TABLE 添加。

仅针对 SQLite，避免在每次新增可空列时都要求开发者 / 运维手动操作。
当未来切换到 PostgreSQL，可在这里分流到 Alembic。
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)


# 表名 → 需要存在的列列表 [(col_name, sql_type_with_default)]
# 注意：SQL 类型必须能被 ALTER TABLE ADD COLUMN 接受
# 新增可空列时不需要 DEFAULT；如需 DEFAULT 直接写 `BOOLEAN DEFAULT 0`
REQUIRED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "message": [
        ("fallback", "BOOLEAN"),  # W10：标记此 assistant 消息是否经过 patch fallback
    ],
}


async def ensure_schema(engine: AsyncEngine) -> None:
    """对所有 REQUIRED_COLUMNS 中的表，检测列是否存在；缺失则 ALTER TABLE 添加。

    幂等：已存在不重复加。仅支持 SQLite（用 PRAGMA table_info）。
    """
    async with engine.begin() as conn:
        for table, cols in REQUIRED_COLUMNS.items():
            # 表不存在则跳过（init_db 会负责创建）
            res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
                {"n": table},
            )
            if res.first() is None:
                continue

            res = await conn.execute(text(f"PRAGMA table_info({table})"))
            present = {row[1] for row in res}
            for col_name, col_type in cols:
                if col_name not in present:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    )
                    log.info(
                        "[db-migrate] added column %s.%s (%s)",
                        table, col_name, col_type,
                    )
