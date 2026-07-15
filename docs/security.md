# API Key 安全管理规范

> V2-F.2 起执行。防止 API Key 泄露导致费用损失（如 2026-07-08 DeepSeek Key 泄露事件）。

## 1. Key 存放位置

| 位置 | 用途 | 安全级别 |
|---|---|---|
| `backend/.env` | 唯一存放 LLM API Key 的文件 | **保密**，已加 .gitignore |
| `/opt/t2g/secrets/*.pem` | Alipay 密钥文件 | **保密**，已加 .gitignore |
| `backend/.env.example` | 占位符模板（如 `sk-xxxxx`） | 公开，不含真实 Key |

**绝对不要**：
- 把真实 Key 写到 `.env.example`
- 创建 `model_config.md` 等含明文 Key 的文件
- 在任何 AI 对话（ChatGPT / Claude / GLM 等）里贴真实 Key
- 在 GitHub Issue / PR / Commit message 里贴真实 Key

## 2. Git 防护

### pre-commit hook

仓库根目录 `.githooks/pre-commit` 会自动检测：
- staged changes 里是否有 `sk-` / `ark-` 开头 20+ 字符的字符串
- staged changes 里是否有 `.env` / `model_config*.md` / `*.pem` 文件

命中则拒绝 commit。

### 启用方式

clone 后执行一次（只需一次）：
```bash
git config core.hooksPath .githooks
```

### .gitignore 规则

已加以下模式：
```
backend/.env
backend/model_config*.md
secrets/
*.pem
*_private_key*.txt
```

## 3. Key 轮换

建议每月轮换一次 LLM Key（DeepSeek / 火山 / MiniMax / Moonshot）。

轮换步骤：
1. 在厂商控制台创建新 Key
2. 更新服务器 `backend/.env`
3. 重启 backend：`docker compose up -d backend`
4. 在厂商控制台删除旧 Key

## 4. 配额限流（V2-F.2）

即使 Key 再次泄露，配额限流也能限制损失：
- 未登录用户：不能使用（强制登录）
- free 用户：每日 5 张图
- pro 用户：无限
- admin 可通过 SQL 调整 per-user 配额（`daily_graph_limit_override`）

## 5. 审计日志

所有 chat 调用都记录审计日志（`audit_log` 表 `chat.send` 事件），含：
- user_id / email
- nl_length（不记原始内容，保护隐私）
- provider
- plan_code / used_today / daily_limit

admin 可通过 `GET /api/audit-log?action=chat.send` 查询。
