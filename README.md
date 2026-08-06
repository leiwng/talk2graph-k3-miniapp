# 话图 T2G 微信小程序版（已归档）

> **⚠️ 本仓库已合并入 [talk2graph-glm](https://github.com/leiwng/talk2graph-glm)（monorepo：backend + frontend + miniapp），不再单独维护。**
> 小程序代码现位于主仓库的 `miniapp/` 目录。本仓库保留仅作历史查阅（归档于 2026-08-06，对应 V1.2 合并）。

---

# 话图 T2G (talk2graph-glm)

用自然语言画数学图形。跟 AI 说「画一个内切圆半径为 3 的等腰三角形」，它就画出来。持续修改，精确控制。

> **在线试用**：https://t2g.yinhour.com（腾讯云 + HTTPS；首次访问按 Ctrl+F5 强制刷新）
>
> **当前版本**：V3.5 · Admin 批量操作 + 飞书 SMTP + 微信文档
> **测试**：342/342 通过

- **后端**：Python + FastAPI + scipy（约束求解 + 自适应重启）+ AST 安全表达式沙箱
- **前端**：React + TypeScript + Vite + Zustand + react-router-dom + SVG
- **LLM**：火山方舟 GLM-5.2 / DeepSeek v4-flash / MiniMax-M3 / 智谱（可切换；当前默认火山方舟 GLM-5.2）
- **存储**：SQLite（用户体系 + 会话持久化 + 审计日志 + 付费订阅 + 邮箱验证码 + 密码重置令牌 + 老师反馈；schema 变更自动迁移）
- **用户体系**：邮箱+密码注册登录 / 微信扫码登录 / JWT 鉴权 / 邮箱验证码 / 密码重置 / 配额限流（free 5/天 / pro 30/天）/ Alipay 电脑网站支付 / Admin 后台 + 批量操作
- **支持范围**：初中平面几何 + 直角坐标系 + 4 种几何变换 + 显式函数图像 + on_curve 硬约束 + 半平面方位 + patch fallback + solve repair + 立体几何（cube/cuboid/cylinder/cone/sphere）+ 统计图表（条形/折线/扇形）+ 弧/扇形/弓形/圆环扇环
- **不在支持范围**：椭圆双曲线一般式（隐式）/ 三视图 / 棱柱棱锥 / 立体截面 / 直方图 / 散点图 - AI 会主动拒绝并给出友好提示

## 当前进度

| 里程碑 | 状态 | Tag | 说明 |
|---|---|---|---|
| W1 - DSL + 求解器 + SVG 渲染 | ✅ | - | 5 个端到端测试 |
| W2 - LLM 抽象层 + Prompt | ✅ | - | 9 个测试；14+ 条中文 few-shot |
| W3 - DSL diff + 会话 + API | ✅ | - | 12 个测试 |
| W4 - 前端 MVP | ✅ | - | React + Vite 三栏布局 |
| W5 - 扩展约束 + 渲染装饰 + 交互 | ✅ | - | 中点/垂足/角平分线/共圆/平行四边形 |
| W6 - 内测打磨 + Docker 部署 | ✅ | - | 30 个测试；错误分类、admin stats |
| W7 - 试用前发布打磨 | ✅ | - | 👍/👎 反馈、乐观更新、拒绝分色 |
| W8 - 生产部署 | ✅ | - | 腾讯云 + COS 每日备份 |
| W9 - V2-A 坐标系 | ✅ | v0.9.0 | axis 对象 + 网格/箭头/刻度 |
| W10 - 半平面 + patch fallback + 自动迁移 | ✅ | v0.10.0 | same_side/opposite_side、DB 自动加列 |
| W11 - 几何变换 | ✅ | v0.11.0 | 4 种变换 + 派生对象机制（虚线+撇） |
| V2-B - 函数图像 | ✅ | v0.12.0 | 显式函数曲线 + AST 沙箱 + 断点切段 |
| W12 - on_curve 硬约束 | ✅ | v0.12.1 | 点在曲线上硬约束 + hint 残差分离 |
| W13-A - 求解器自适应重启 | ✅ | v0.13.0 | restarts_extra + 4 种初值策略 |
| W13-B - 约束诊断 + LLM 二次修复 | ✅ | v0.13.1 | solve_repair 回路 + 歧义处理 prompt |
| V2-C - PPT 字体 outline 化 | ✅ | - | 导出 SVG/PNG/PDF 时 text->path，跨平台字体一致 |
| V2-D - SSE token-level 流式 | ✅ | - | LLM 阻塞期间实时推送 token + 已识别对象列表 |
| V2-E - 多 Provider 评测 + UI/UX 打磨 + 自动 Fallback | ✅ | - | 5 家评测 + 教育蓝 UI + fallback chain |
| V2-F.1 - 用户体系 + 审计骨架 | ✅ | - | JWT + 邮箱登录 + 审计 + admin 权限 |
| V2-F.2 - 付费 + 配额限流 + 安全加固 | ✅ | - | Alipay + 配额 + 强制登录 + pre-commit hook |
| V2-G.1 - 弧 + 扇形 + 正多边形 + 梯形 | ✅ | - | arc/sector/regular_polygon/trapezoid |
| V2-G.2 - 圆弧角度 / 弧长 / 弓形面积约束 | ✅ | - | arc_angle/arc_length/bow_area |
| V2-G.3 - 阴影区域 / 数轴 / 网格 / 辅助线 | ✅ | - | region/number_line/aux_line + grid_size |
| V2-G.4 - 分段函数 / 位似 / 弓形 / 标注 | ✅ | - | curve.pieces + homothety + bow + arc_length/bow_area 标注 |
| V3.0 - 立体几何 + 统计图表 | ✅ | - | cube/cuboid/cylinder/cone/sphere + bar/line/pie chart |
| V3.1 P0 - 历史会话侧抽屉 | ✅ | - | SessionDrawer + 行内编辑 + 自动 title |
| V3.2 P1 - 邮箱验证码 + WeChat OAuth + SMTP | ✅ | - | 邮箱验证 + 密码重置 + 微信扫码 |
| V3.3 P2 - Admin 管理界面 | ✅ | - | 6 个 admin 页面 + 配额覆盖 + 订阅管理 |
| V3.4 P3 - 圆环扇环 | ✅ | - | annular_sector 对象 |
| **V3.5 - Admin 批量操作 + 飞书 SMTP + 微信文档** | ✅ | - | 批量 4 种 action + SMTPProvider + 文档 |

**累计 342 个测试通过。**

## 后端快速上手

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 跑全部 149 个测试
pytest -q

# 启动 API（默认 8000）
uvicorn app.main:app --reload --port 8000
```

> **首次启动会自动创建 `data/talk2graph.db`**（SQLite）。如果你之前升级过 schema（如 W7 加入 `error_kind` 列与 `feedback` 表），开发期可直接 `rm data/talk2graph.db` 让 `init_db()` 重建；生产部署建议引入 Alembic 迁移。

## 前端快速上手

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

详细见 `frontend/README.md`。**先启后端再启前端**；Vite 已配 `/api` 代理。

## 小程序快速上手（miniapp/）

```bash
# 1. 先启后端（本机 macOS 用这个脚本：注入 Homebrew cairo 库路径，PNG 导出才工作；
#    --reload 改代码自动重载，但改 .env 后仍需手动重启）
backend/scripts/dev-local.sh    # 默认 8080 端口

# 2. 后端 .env 配置小程序 AppID（登录用）
WECHAT_MINIAPP_APP_ID=...
WECHAT_MINIAPP_APP_SECRET=...
```

3. 微信开发者工具「导入项目」选择 `miniapp/` 目录
4. 详情 → 本地设置 → 勾选「不校验合法域名…」（开发期直连 `http://127.0.0.1:8000`，见 `miniapp/config.js`）
5. 编译后点「微信一键登录」即可使用

生产期：`miniapp/config.js` 的 `API_BASE` 改为 HTTPS 域名，并在小程序后台配置 request / downloadFile 合法域名。

## LLM Provider 配置

后端通过 `.env` 读取 Key、Base URL、模型名，全部支持环境变量覆盖：

```bash
DEFAULT_PROVIDER=volcengine

# 火山方舟（承载 GLM-5.2）
VOLCENGINE_API_KEY=...
VOLCENGINE_ENDPOINT_ID=glm-5.2
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3

# DeepSeek
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-v4-flash       # 推理模型 v4-pro 太慢，建议 v4-flash

# MiniMax
MINIMAX_API_KEY=...
MINIMAX_MODEL=MiniMax-M3

# 智谱（可选）
ZHIPU_API_KEY=...
ZHIPU_MODEL=glm-5.2
```

完整配置见 `backend/.env.example`。

> **注意**：火山方舟 `coding/v3` endpoint 不支持 `response_format=json_object`，`VolcengineProvider.supports_json_mode = False`，改靠 system prompt 约束 JSON 输出。

## 生产部署（腾讯云 + HTTPS 域名）

```bash
cp backend/.env.example backend/.env
# 编辑 .env 填入：
#   - LLM API Key（火山方舟 / DeepSeek / MiniMax / 智谱）
#   - T2G_JWT_SECRET（openssl rand -hex 32）
#   - T2G_BOOTSTRAP_ADMIN_EMAIL / T2G_BOOTSTRAP_ADMIN_PASSWORD（首次启动后可删）
#   - Alipay 配置（ALIPAY_APP_ID / 密钥文件路径 / 网关 URL）

# HTTP 8080 端口（试用期）
./deploy/bootstrap.sh

# HTTPS 域名（t2g.yinhour.com，需备案）
T2G_DOMAIN=t2g.yinhour.com ./deploy/bootstrap.sh
```

**密钥文件**：Alipay 密钥放宿主机 `/opt/talk2graph-glm/secrets/`，docker-compose 自动挂载到容器 `/app/secrets/`。

**首次 clone 后启用 pre-commit hook**：
```bash
git config core.hooksPath .githooks
```

完整步骤、HTTPS、COS 备份见 [`deploy/README.md`](deploy/README.md)；安全组放行清单见 [`deploy/firewall.md`](deploy/firewall.md)；日常运维 SOP 见 [`docs/operations.md`](docs/operations.md)；API Key 安全规范见 [`docs/security.md`](docs/security.md)。

## 关键能力清单

### DSL 已支持

- **对象**：点、线段、直线、多边形、圆（4 种定义：center+radius / center+through / 内切圆 / 外接圆）
- **约束（17 类）**：长度、等长、角度、平行、垂直、共线、相切、点在圆上、等腰、等边、直角三角形、半径、**中点、垂足、角平分线、共圆、平行四边形**

### 渲染装饰（自动根据约束生成）

- 直角小方块（`right_triangle` / `perpendicular`）
- 等长刻度（`equal_length` / `equilateral` / `isoceles`，1/2/3 道分组）
- 角度弧（`angle` 非 90° 时绘制）
- 中文/LaTeX 标签

### 前端交互

- 三栏布局：对话 / 画板 / 对象树+属性
- **输入立即显示** + 「话图正在思考中…」占位气泡（动画）
- LLM 拒绝消息按类型分色：拒绝=黄、求解失败=紫、网络/鉴权=红
- Provider 一键切换（localStorage 持久化）
- 撤销 / 重做（后端返回 SVG，画板实时同步）
- 属性面板：改约束数值、删约束、改标签、查看坐标
- 画板 hover 高亮 + tooltip
- 画板拖动点（产生 `hint` 软约束 → 重解）
- 画板右下角 **👍 不错 / 👎 不对** 反馈按钮
- 导出 SVG / PNG / PDF

### 数据持久化

- `user` / `session`（含 user_id FK）/ `message`（含 error_kind）/ `dsl_snapshot` / `feedback`
- `audit_log`（actor_id / action INDEX / metadata_json / ip_address / user_agent）
- `subscription_plan` / `subscription_order` / `user_subscription`（含 daily_graph_limit_override）
- 老师 NL、AI 回复、错误分类、反馈评分与评论全部入库
- 每次 chat 作图审计：action=chat.send，含 plan/used_today/daily_limit（fire-and-forget，best-effort）
- `GET /api/admin/stats?days=N` 用量统计（admin only）
- `GET /api/admin/feedback?days=N` 反馈列表（admin only）
- `GET /api/admin/feedback.jsonl?days=N` 下载导出（admin only）
- `GET /api/audit-log` 审计日志查询（admin only，分页 + 多维过滤）

## 项目结构

```
backend/
├── app/
│   ├── dsl/         # 几何 DSL：schema + validator + diff（17 类约束）
│   ├── solver/      # 数值约束求解器（scipy.least_squares + hint 软约束）
│   ├── render/      # SVG 渲染 + 几何装饰（直角小方块/等长刻度/角度弧）+ text_to_path
│   ├── llm/         # Provider 抽象 + 火山/DeepSeek/MiniMax/智谱 + Prompt + 抽取器 + fallback chain
│   ├── auth/        # 用户鉴权：password(bcrypt) + jwt_token + deps + repository
│   ├── audit/       # 审计日志：actions + repository（fire-and-forget）
│   ├── payment/     # 付费：plans + alipay(RSA2) + subscription + entitlement + repository
│   ├── db/          # SQLite (SQLAlchemy async)：user/session/message/snapshot/feedback/audit_log/subscription_*
│   ├── session/     # 会话仓库 + undo/redo + 反馈
│   ├── api/         # FastAPI 路由（session/chat/export/providers/admin/auth/audit_log/payment/webhooks）+ 错误分类
│   └── main.py
├── scripts/         # eval_cmm.py / rewrite_v2.py / compare_v1_v2r.py
├── tests/           # 219 个测试
├── Dockerfile
└── pyproject.toml

frontend/
├── src/
│   ├── api/         # types + client(SSE) + auth(登录/token) + payment(订阅)
│   ├── store/       # Zustand 全局状态（app + auth 独立 store）
│   ├── pages/       # LoginPage / RegisterPage / ForgotPasswordPage / AccountPage / ChangePasswordPage / PricingPage / SubscriptionPage
│   ├── components/  # TopBar / ChatPanel / Canvas / RightPanel / ProviderSwitch + auth/（UserMenu/ProtectedRoute/AuthPageShell）
│   ├── App.tsx      # react-router-dom 路由（/ /login /register /forgot-password /pricing /app /account /account/password /account/subscription）
│   └── styles.css
├── Dockerfile       # nginx 多阶段镜像
├── nginx.conf       # /api ^~ 前缀反代到 backend:8000
└── vite.config.ts

deploy/
├── bootstrap.sh     # 一键部署（T2G_DOMAIN 启用 HTTPS / T2G_GIT_MIRROR 镜像）
├── backup-db.sh     # SQLite -> 腾讯云 COS
├── Caddyfile        # 自动 HTTPS（profile=https 启用）
├── firewall.md      # 腾讯云安全组放行清单
└── README.md        # 腾讯云部署完整文档（含 HTTPS + Alipay 配置）

docs/
├── onboarding.md    # 给下一个 AI / 接手者的入门
├── operations.md    # 生产运维 SOP（日常/升级/回滚/应急）
├── security.md      # API Key 安全管理规范（V2-F.2）
└── teacher-guide.md # 老师内测说明（含示例 prompt）

.githooks/
└── pre-commit       # 检测 sk-/ark- 开头 20+ 字符的 API Key + .env/model_config*.pem（V2-F.2）

test/
├── cmm_test_v1_original.json     # CMM 数据集 56 条原题
├── cmm_test_v2_rewritten.json    # 改写后（明确作图指令）
└── 测试数据集.md

secrets/             # Alipay 密钥文件（.gitignore，挂载到容器 /app/secrets/）
├── app_private_key.pem
└── alipay_public_key.pem

.github/ISSUE_TEMPLATE/  # bug-report + feature-request

CHANGELOG.md
docker-compose.yml   # backend + frontend + caddy(https profile) + secrets volume
```

## License

MIT

---

## 接手 / 续作指南

**新一轮对话开始时**，请先读 [`docs/onboarding.md`](docs/onboarding.md)（给下一个 AI 或接手者的入门文档），
再看 [`CHANGELOG.md`](CHANGELOG.md) 顶部最新里程碑块，了解当前状态。

每次完成变更后，需要在 `CHANGELOG.md` **顶部**追加新版本块以保持一致性。
