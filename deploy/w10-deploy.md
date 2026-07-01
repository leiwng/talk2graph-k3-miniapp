# W10 上线腾讯云操作手册

> 目标：把 W8 → W10（跳过 W9 独立发布）。测试 78 → 103。
>
> **DB schema 变更**：新增 `message.fallback` 列。启动时 `ensure_schema()` 自动加列，**无需手动 SQL**。

## 一句话升级（99% 情况）

```bash
ssh <user>@49.233.15.73
cd ~/talk2graph-glm
./deploy/bootstrap.sh
```

bootstrap.sh 会自动：
1. `git fetch origin main` → 拉到 v0.10.0（含 commit ecc5ee7）
2. `git reset --hard origin/main`
3. `docker compose build` → 用清华 pip + 淘宝 npm 镜像重建
4. `docker compose up -d` → 后端启动时 `ensure_schema()` 加 fallback 列
5. `curl /api/health` 直到 30 次 × 2s = 60s 内就绪

## 事前准备（推荐做，5 分钟）

### 1. 备份 DB
```bash
cd ~/talk2graph-glm
docker exec t2g-backend sh -c "cp /app/data/talk2graph.db /app/data/backups/pre-w10-$(date +%Y%m%d-%H%M%S).db"
# 确认备份
docker exec t2g-backend ls -lh /app/data/backups/
```

### 2. 记录当前 tag（方便回滚）
```bash
git -C ~/talk2graph-glm describe --tags --always
# 期望：v0.8.0 或提交哈希；记下来
```

### 3. 观察当前老师是否在用（可选）
```bash
docker logs --tail 50 t2g-backend
```
如果看到 llm.chat 活动，等 10 分钟到低峰期再升级。

## 执行升级

```bash
cd ~/talk2graph-glm
./deploy/bootstrap.sh
```

## 升级后立即验证（3 步）

### 1. 健康检查
```bash
curl -s http://localhost:8080/api/health
# 期望：{"status":"ok","version":"0.3.0"}
```

### 2. 验证 DB 迁移生效
```bash
docker exec t2g-backend sqlite3 /app/data/talk2graph.db "PRAGMA table_info(message);" | grep fallback
# 期望：11|fallback|BOOLEAN|0||0
```
如果 grep 空，说明 ensure_schema 没跑，看日志：
```bash
docker logs t2g-backend | grep -E "db-migrate|ensure_schema|Traceback"
```

### 3. 端到端手测 3 句
在浏览器打开 `http://49.233.15.73:8080/`（务必 Ctrl+F5 强制刷新，清掉旧 JS 缓存），点「+ 新会话」，然后：

| # | 输入 | 期望 |
|---|---|---|
| A | 画一个平面直角坐标系 | ✅ 出现坐标系 |
| B | 画直角三角形 ABC，C 为直角顶点，C 在 AB 上方，BC=3，CA=4 | ✅ C 在 AB 上方 |
| C | 画一个等边三角形 ABC，边长为 4 | ✅ 老题不退化 |

## 常见问题 & 应急

### git fetch 失败（国内 GitHub 抖动）
```bash
T2G_GIT_MIRROR=https://kkgithub.com/leiwng/talk2graph-glm.git ./deploy/bootstrap.sh
```

### docker build 慢 / 卡在 pip
清华镜像已配好；如果还卡，检查网络：
```bash
docker compose logs --tail 100
```

### 部署后前端仍显示旧文案（"暂不支持基于坐标的描述"）
**这是浏览器缓存**。用户需要 Ctrl+F5 强制刷新，或用隐私窗口打开。
你可以在 nginx 前面加 `Cache-Control: no-cache` 头缓解，但目前不必。

### fallback 列没有加成功
```bash
# 手动加
docker exec t2g-backend sqlite3 /app/data/talk2graph.db \
  "ALTER TABLE message ADD COLUMN fallback BOOLEAN;"
# 重启
docker compose restart backend
```

### 需要回滚到 W8
```bash
cd ~/talk2graph-glm
git checkout v0.8.0  # 或之前记的 tag
docker compose up -d --build
# fallback 列会残留在 DB 中但 W8 代码不读它，兼容
```

若要**彻底**回滚 DB：
```bash
docker exec t2g-backend cp /app/data/backups/pre-w10-<timestamp>.db /app/data/talk2graph.db
docker compose restart backend
```

## 部署完成后要做的事

1. 在 `docs/operations.md` 记一笔"W10 上线 YYYY-MM-DD"
2. 如果有老师在用，可以主动告知本次新能力：
   - 「C 在 AB 上方」这类方位描述现在能稳定画对
   - 修改图形时不再看到"图形不合法"的突兀错误
3. 下次遇到问题时用 `docker logs t2g-backend --tail 200` 抓日志
