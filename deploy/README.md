# 话图 T2G 部署指南（腾讯云轻量应用服务器）

> 当前状态：**W8 — 生产部署**。
> 实际部署到的服务器 IP / 域名请由部署执行人填回 `README.md` 与 `CHANGELOG.md` 顶部块。

---

## 0. 凭据安全（部署前必读）

| 凭据 | 用途 | 存放位置 | **绝对不要** |
|---|---|---|---|
| 腾讯云子账号密码 | 控制台 | 浏览器密码管理器 | 贴到 Issue / 对话 / Git |
| 腾讯云 SecretId/SecretKey（部署用，可选） | 命令行管理资源 | 本机 `~/.tencentcloudcli` | 进 Docker 镜像、写仓库 |
| **COS 子用户 SecretId/SecretKey**（备份用，必须） | 仅 PutObject 到 `talk2graph-1259138134` | 服务器 `~/.coscli.yaml` | 任何会 push 的目录 |
| 火山方舟 API Key | 后端调 LLM | 服务器 `/opt/talk2graph-glm/backend/.env` | git、对话、日志 |

**只要凭据曾出现在与 LLM 的对话窗口里，就视为已外泄，必须立刻在控制台禁用并重新生成。**

最小化权限建议：
- 部署/管理：单独子账号（如 `talk2graph-deploy`），仅授权所需资源
- COS 备份：再建一个**只读不可登录的程序型子用户**，CAM 策略只给 `cos:PutObject` + `cos:GetService` 限定到 `talk2graph-1259138134`

---

## 1. 服务器准备

推荐：

| 项 | 配置 |
|---|---|
| 类型 | **腾讯云轻量应用服务器** |
| 规格 | 2C4G 起步（约 ¥60-80/月） |
| 地域 | **北京**（与火山方舟同区，减少回程延迟） |
| 镜像 | Ubuntu 22.04 LTS（带 Docker 镜像更省事，也可纯 Ubuntu 后让 `bootstrap.sh` 自动装） |
| 带宽 | ≥ 3Mbps |
| 域名 | 可选；MVP 试用阶段先用 IP+8080 |

控制台快捷登录（你的子账号）：
https://cloud.tencent.com/login/subAccount/100010057940?type=subAccount&username=talk2graph-deploy

⚠ COS（如 `talk2graph-1259138134`）**不能跑后端**，只是对象存储；运行 backend 必须有一台**虚拟机**（轻量服务器或 CVM）。

---

## 2. 端口与备案策略

| 端口 | 用途 | 国内是否需要 ICP 备案 |
|---|---|---|
| 22 | SSH | 否 |
| **8080** | 试用期 HTTP 入口（默认） | **否** ← MVP 选这个 |
| 80 | 标准 HTTP | **是**，未备案时会被运营商干扰 |
| 443 | HTTPS（域名+Caddy） | 域名需备案；证书自动 |

MVP 内测期先用 `http://<公网IP>:8080`，省掉 7-20 天的备案等待。
等老师试用稳定、准备公开发布时再走域名 + 443 + 备案。

---

## 3. SSH 初始化服务器

SSH 登录后：

```bash
sudo apt update
sudo apt install -y git curl ca-certificates sqlite3
sudo mkdir -p /opt/talk2graph-glm
sudo chown $USER:$USER /opt/talk2graph-glm
cd /opt
git clone https://github.com/leiwng/talk2graph-glm.git
cd talk2graph-glm
```

---

## 4. 配置 LLM Key（火山方舟 GLM-5.2）

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

至少配火山方舟，**Key 在 nano 里手输入，永远不要发到对话或 Issue**：

```bash
DEFAULT_PROVIDER=volcengine

# 火山方舟（承载 GLM-5.2）
VOLCENGINE_API_KEY=REMOVEDxxxxx
VOLCENGINE_ENDPOINT_ID=glm-5.2
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
```

> 火山方舟 `coding/v3` endpoint **不支持** `response_format=json_object`，
> `VolcengineProvider.supports_json_mode = False`（已写死），改靠 system prompt 约束 JSON。

---

## 5. 一键部署

```bash
chmod +x deploy/bootstrap.sh
./deploy/bootstrap.sh
```

脚本会：
- 必要时自动装 Docker
- 创建持久化目录 `data/db`、`data/logs`、`data/backups`
- 保留现有 DB（不会误删；如确需重置：`T2G_RESET_DB=1 ./deploy/bootstrap.sh`，会先备份）
- `docker compose build && up -d`
- 通过宿主 8080 端口 `curl /api/health` 做健康检查

成功后访问：`http://<服务器公网 IP>:8080`

如需换端口：`T2G_HOST_PORT=8081 ./deploy/bootstrap.sh`

---

## 6. 自动 HTTPS（域名 + 备案完成后再做）

1. DNS A 记录指向服务器
2. 设环境变量：
   ```bash
   export T2G_DOMAIN=t2g.yourdomain.com
   ```
3. 启用 https profile：
   ```bash
   docker compose --profile https up -d
   ```

Caddy 会自动申请并续期 Let's Encrypt 证书；流量从 80/443 进 → 反代 frontend。

启 https profile 时**不要**同时暴露 frontend 的 8080，否则会和 caddy 抢端口（compose 配置已避免）。

---

## 7. 每日数据库备份到腾讯云 COS

桶：`talk2graph-1259138134`（广州 `ap-guangzhou`）

### 7.1 安装 coscli

```bash
wget https://cosbrowser.cloud.tencent.com/software/coscli/coscli-linux-amd64 -O /tmp/coscli
sudo mv /tmp/coscli /usr/local/bin/coscli
sudo chmod +x /usr/local/bin/coscli
coscli config init
```

`coscli config init` 提示项：
- `Secret ID`：**新建的备份专用子用户**的 SecretId（不要复用部署凭据）
- `Secret Key`：对应 SecretKey
- `App ID`：`1259138134`
- `Region`：`ap-guangzhou`
- `Bucket Alias`：随意，如 `t2g-backup`

测试：
```bash
coscli ls cos://talk2graph-1259138134/
```

### 7.2 配置 cron

```bash
crontab -e
```

加入：

```
T2G_ROOT=/opt/talk2graph-glm
T2G_COS_BUCKET=cos://talk2graph-1259138134
0 3 * * * /opt/talk2graph-glm/deploy/backup-db.sh >> /var/log/t2g-backup.log 2>&1
```

每天凌晨 3 点把 SQLite 备份到 COS，本地保留 7 天。

第二天验收：
```bash
coscli ls cos://talk2graph-1259138134/db/
tail /var/log/t2g-backup.log
```

---

## 8. 日常运维

```bash
# 查看实时日志
docker compose logs -f --tail 200

# 滚动升级（拉最新代码 + 重建，不动 DB）
cd /opt/talk2graph-glm
./deploy/bootstrap.sh

# 看后端结构化日志（JSON，方便 jq）
tail -f data/logs/app.log

# 进 backend 容器调试
docker compose exec backend bash

# 停服
docker compose down

# 完全清理（保留持久化数据）
docker compose down
docker system prune -af
```

---

## 9. 故障排查

| 现象 | 排查 |
|---|---|
| 浏览器打不开 IP:8080 | ① 腾讯云安全组是否放行 8080？② `docker compose ps` 是否 healthy？③ `docker compose logs frontend backend` |
| 502 / 接口报错 | 多半是 backend 容器异常；`docker compose logs backend` |
| LLM 返回 401 | `.env` 里 `VOLCENGINE_API_KEY` 是否正确；该 Key 在火山方舟控制台是否已开通 GLM-5.2 |
| 求解失败（紫色气泡） | 用户问题约束矛盾，正常；高频出现可看 `/api/admin/feedback` |
| AI 拒绝（黄色气泡） | 题型超出 MVP 范围（函数图像/立体/抛物线/坐标/统计图），属于正常 |
| 中文乱码 | 浏览器没问题；导出 SVG 到 PPT 乱码 → V2 字体 outline 化 |
| 升级后旧会话打不开 | DB schema 有变更 → 开发期 `T2G_RESET_DB=1 ./deploy/bootstrap.sh`；生产应停机用 sqlite3 `.dump` + 手动 `ALTER TABLE` 或上 Alembic |

详细运维 SOP 见 [`docs/operations.md`](../docs/operations.md)。

---

## 10. DB Schema 当前状态（W7+W8 一致）

```
session       (id, title, llm_provider, created_at, updated_at, meta_json)
message       (id, session_id, role, content, dsl_patch_json, llm_provider,
               tokens_in, tokens_out, latency_ms, error_kind, created_at)
dsl_snapshot  (id, session_id, seq, dsl_json, solution_json, created_at)
feedback      (id, session_id, snapshot_seq, rating, comment, nl,
               dsl_json, llm_provider, created_at)
```

生产期 schema 升级当前未上 Alembic；要在线升级请：
1. 停机 `docker compose down`
2. 备份 `cp data/db/talk2graph.db data/backups/pre-upgrade.db`
3. 手动 SQL 或重置后让 `init_db()` 重建
4. 启动 `docker compose up -d`

---

## 11. 监控与反馈数据

- **用量统计**：`GET /api/admin/stats?days=N` — 会话/消息/快照数 + 按 Provider 的 tokens 与平均延迟
- **反馈列表（JSON）**：`GET /api/admin/feedback?days=N`
- **反馈导出（JSONL）**：`GET /api/admin/feedback.jsonl?days=N`（浏览器直接下载）

定期把 feedback.jsonl 拉下来分析常见出错题型，反过来迭代 prompt / few-shot。

---

## 12. 老师内测发布清单

1. ✅ 部署成功，外网能访问 `http://<IP>:8080`
2. ✅ 火山方舟 GLM-5.2 Key 已配，能跑题
3. ✅ 隐私页文案（见根 README 数据合规章节）
4. ✅ COS 备份首日已验证（`coscli ls` 能看到产物）
5. ✅ GitHub Issues 模板就绪（`.github/ISSUE_TEMPLATE/`）
6. ✅ 邀请老师试用，发使用说明 `docs/teacher-guide.md`
7. ✅ 第一周每天看一次 `/api/admin/feedback`，回应 👎 评论
