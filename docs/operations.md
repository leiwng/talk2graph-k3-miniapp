# 话图 T2G 生产运维 SOP

> 给接手者或非作者用：日常**怎么看、怎么救、怎么升、怎么回滚**。
> 部署初始化见 [`deploy/README.md`](../deploy/README.md)。

## 1. 服务在哪里

| 资源 | 位置 |
|---|---|
| 服务器 | 腾讯云轻量应用服务器，北京（部署后填实际 IP） |
| 部署根目录 | `/opt/talk2graph-glm` |
| 容器编排 | `docker compose` (`backend` + `frontend` + 可选 `caddy`) |
| 持久化数据 | `data/db/talk2graph.db`（SQLite，每天 3:00 自动备份） |
| 结构化日志 | `data/logs/app.log`（JSON，按天滚动） |
| 备份桶 | COS `cos://talk2graph-1259138134/db/`（ap-guangzhou） |
| LLM Provider | 火山方舟 GLM-5.2 |

## 2. 每天 10 分钟运维例行（W8 试用期）

```bash
ssh <服务器>
cd /opt/talk2graph-glm

# a) 服务还活着吗
docker compose ps
curl -s http://localhost:8080/api/health

# b) 昨天用量
curl -s 'http://localhost:8080/api/admin/stats?days=1' | jq

# c) 老师反馈（特别看 rating=down）
curl -s 'http://localhost:8080/api/admin/feedback?days=1' | jq '.[] | select(.rating=="down")'

# d) 备份昨晚跑了吗
tail -n 20 /var/log/t2g-backup.log
coscli ls cos://talk2graph-1259138134/db/ | tail -5

# e) 最近 50 行错误日志
tail -200 data/logs/app.log | jq -c 'select(.level=="error" or .level=="warning")'
```

## 3. 滚动升级

```bash
cd /opt/talk2graph-glm
./deploy/bootstrap.sh
```

- 自动 `git pull` + 重建镜像 + 重启容器
- DB 保留不动
- 走宿主 8080 做健康检查，30 秒内绿就算成功

## 4. 回滚

### 4.1 代码回滚

```bash
cd /opt/talk2graph-glm
git log --oneline -10
git checkout <good-commit-sha>
./deploy/bootstrap.sh
```

### 4.2 数据回滚

```bash
# 停服
docker compose down

# 从 COS 拉最近一份备份
coscli ls cos://talk2graph-1259138134/db/ | tail -10
coscli cp cos://talk2graph-1259138134/db/talk2graph-YYYYMMDD-HHMMSS.db \
          /opt/talk2graph-glm/data/db/talk2graph.db

# 启动
docker compose up -d
```

### 4.3 紧急下线

```bash
docker compose down
# 浏览器会自然 502，老师看到也合理
```

## 5. DB Schema 变更（生产）

**当前未上 Alembic**，每次涉及 `app/db/models.py` 的变更要走以下流程：

1. 通知所有使用者预定停机窗口（建议夜间）
2. 备份现有 DB
   ```bash
   docker compose down
   cp data/db/talk2graph.db data/backups/pre-$(date +%Y%m%d-%H%M%S).db
   ```
3. 手动跑 SQL（参考 CHANGELOG 顶部"DB Schema 升级"段）
   ```bash
   sqlite3 data/db/talk2graph.db
   sqlite> ALTER TABLE message ADD COLUMN error_kind VARCHAR(16);
   ```
4. 启动验证
   ```bash
   ./deploy/bootstrap.sh
   ```
5. 失败可用步骤 2 的备份回滚

未来上 Alembic 后此节简化为 `alembic upgrade head`。

## 6. LLM Key 轮换

```bash
nano /opt/talk2graph-glm/backend/.env
# 修改 VOLCENGINE_API_KEY=新值

# 让 backend 容器重载 env
docker compose restart backend

# 验证
curl -s 'http://localhost:8080/api/providers' | jq
```

不要 `git commit` `.env`（已在 .gitignore）。

## 7. 监控触发的应急动作

| 信号 | 含义 | 动作 |
|---|---|---|
| `/api/health` 持续 5xx | 容器挂了 | `docker compose restart backend` |
| `app.log` 出现密集 `network` 错误 | LLM 服务降级 | 看火山方舟控制台状态页；必要时改 `DEFAULT_PROVIDER=deepseek` 切备份 Provider |
| 反馈 rating=down 集中在某题型 | Prompt/few-shot 不够好 | 把样例加入 `backend/app/llm/prompts/fewshots.jsonl` → 跑 `pytest -q` → 升级 |
| 备份脚本连续 2 天失败 | coscli 配置或 COS 密钥过期 | `coscli ls cos://...` 试一下，必要时 `coscli config init` 重配 |
| 磁盘占用 > 80% | 日志或备份积压 | `du -sh data/*`；清理 7 天以上备份；切日志滚动 |

## 8. 关键文件清单（出问题先看这些）

| 路径 | 用途 |
|---|---|
| `/opt/talk2graph-glm/backend/.env` | LLM Key、Provider 配置 |
| `/opt/talk2graph-glm/data/db/talk2graph.db` | 主数据库 |
| `/opt/talk2graph-glm/data/logs/app.log` | 结构化日志 |
| `/var/log/t2g-backup.log` | 备份脚本日志 |
| `/etc/crontab` 或 `crontab -l` | 定时任务 |
| `/usr/local/bin/coscli` + `~/.coscli.yaml` | COS 备份工具 |

## 9. 联系人 / 责任

| 角色 | 联系 |
|---|---|
| 产品 + 开发主 | （部署后填） |
| 运维兜底 | （部署后填） |
| 老师试用对接 | （部署后填） |
| LLM Provider（火山方舟）账户 | 工单：https://console.volcengine.com/workorder/create |
| 腾讯云账户 | 工单：腾讯云控制台 → 工单管理 |

## 10. 何时该升 V2

试用满 1 个月，如果出现：
- 函数图像 / 圆锥曲线题占拒绝率 > 30%
- 老师反复反馈"我想画坐标系"
- 周用量 > 200 题

→ 触发 V2 路线图（CHANGELOG 末尾），具体节奏与作者讨论。
