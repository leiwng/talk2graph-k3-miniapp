"""审计日志：所有敏感操作（登录/登出/改密/每次 chat 作图）的写入与查询。

写入走 fire-and-forget，失败仅 logger.warning，永不阻塞主流程。
借鉴 Lumiton AuditLogRepository 的 best-effort 模式。
"""
