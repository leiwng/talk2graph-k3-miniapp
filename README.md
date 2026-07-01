# 话图 T2G (talk2graph-glm)

用自然语言画数学图形。跟 AI 说「画一个内切圆半径为 3 的等腰三角形」，它就画出来。持续修改，精确控制。

> **在线试用**：`http://49.233.15.73:8080`（腾讯云；首次访问按 Ctrl+F5 强制刷新）
>
> **当前版本**：v0.12.0 · V2 主线完成（平面几何 + 坐标系 + 几何变换 + 函数图像）

- **后端**：Python + FastAPI + scipy（约束求解）+ AST 安全表达式沙箱
- **前端**：React + TypeScript + Vite + Zustand + SVG
- **LLM**：火山方舟 GLM-5.2 / DeepSeek v4-flash / MiniMax-M3 / 智谱（可切换；当前默认火山方舟 GLM-5.2）
- **存储**：SQLite（免登录，会话持久化；老师反馈持久化；schema 变更自动迁移）
- **支持范围**：初中平面几何 + 直角坐标系 + 4 种几何变换（旋转/平移/对称/中心对称）+ 显式函数图像 y=f(x)
- **不在支持范围**：立体几何 / 椭圆双曲线一般式（隐式）/ 统计图表 — AI 会主动拒绝并给出友好提示

## 当前进度

| 里程碑 | 状态 | Tag | 说明 |
|---|---|---|---|
| W1 — DSL + 求解器 + SVG 渲染 | ✅ | — | 5 个端到端测试 |
| W2 — LLM 抽象层 + Prompt | ✅ | — | 9 个测试；14+ 条中文 few-shot |
| W3 — DSL diff + 会话 + API | ✅ | — | 12 个测试 |
| W4 — 前端 MVP | ✅ | — | React + Vite 三栏布局 |
| W5 — 扩展约束 + 渲染装饰 + 交互 | ✅ | — | 中点/垂足/角平分线/共圆/平行四边形 |
| W6 — 内测打磨 + Docker 部署 | ✅ | — | 30 个测试；错误分类、admin stats |
| W7 — 试用前发布打磨 | ✅ | — | 👍/👎 反馈、乐观更新、拒绝分色 |
| W8 — 生产部署 | ✅ | — | 腾讯云 + COS 每日备份 |
| **W9 — V2-A 坐标系** | ✅ | v0.9.0 | axis 对象 + 网格/箭头/刻度 |
| **W10 — 半平面 + patch fallback + 自动迁移** | ✅ | v0.10.0 | same_side/opposite_side、DB 自动加列 |
| **W11 — 几何变换** | ✅ | v0.11.0 | 4 种变换 + 派生对象机制（虚线+撇） |
| **V2-B — 函数图像** | ✅ | v0.12.0 | 显式函数曲线 + AST 沙箱 + 断点切段 |

**累计 134 个测试通过。**

## 后端快速上手

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 跑全部 134 个测试
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

## 生产部署（腾讯云）

```bash
cp backend/.env.example backend/.env
# 编辑 .env 填入火山方舟 API Key 与 GLM-5.2 endpoint
./deploy/bootstrap.sh                    # 默认对外 8080 端口
T2G_HOST_PORT=8081 ./deploy/bootstrap.sh # 自定义端口
```

完整步骤、HTTPS、COS 备份见 [`deploy/README.md`](deploy/README.md)；安全组放行清单见 [`deploy/firewall.md`](deploy/firewall.md)；日常运维 SOP 见 [`docs/operations.md`](docs/operations.md)。

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

- `session` / `message`（含 `error_kind`）/ `dsl_snapshot` / `feedback`
- 老师 NL、AI 回复、错误分类、反馈评分与评论全部入库
- `GET /api/admin/stats?days=N` 用量统计
- `GET /api/admin/feedback?days=N` 反馈列表
- `GET /api/admin/feedback.jsonl?days=N` 下载导出

## 项目结构

```
backend/
├── app/
│   ├── dsl/         # 几何 DSL：schema + validator + diff（17 类约束）
│   ├── solver/      # 数值约束求解器（scipy.least_squares + hint 软约束）
│   ├── render/      # SVG 渲染 + 几何装饰（直角小方块/等长刻度/角度弧）
│   ├── llm/         # Provider 抽象 + 火山/DeepSeek/MiniMax/智谱 + Prompt + 抽取器
│   ├── db/          # SQLite (SQLAlchemy async)：session/message/snapshot/feedback
│   ├── session/     # 会话仓库 + undo/redo + 反馈
│   ├── api/         # FastAPI 路由（session/chat/export/providers/admin）+ 错误分类
│   └── main.py
├── scripts/         # eval_cmm.py / rewrite_v2.py / compare_v1_v2r.py
├── tests/           # 76 个测试（W1-W7）
├── Dockerfile
└── pyproject.toml

frontend/
├── src/
│   ├── api/         # 类型（含 error_kind）+ fetch 封装
│   ├── store/       # Zustand 全局状态 + 乐观更新 + localStorage
│   ├── components/  # TopBar / ChatPanel（按 error_kind 分色）/ Canvas（hover/drag/反馈） / RightPanel / ProviderSwitch
│   ├── App.tsx
│   └── styles.css
├── Dockerfile       # nginx 多阶段镜像
├── nginx.conf       # /api 反代到 backend:8000
└── vite.config.ts

deploy/
├── bootstrap.sh     # 一键部署 / 升级（T2G_HOST_PORT 参数化，幂等不删 DB）
├── backup-db.sh     # SQLite → 腾讯云 COS（默认桶 talk2graph-1259138134）
├── Caddyfile        # 自动 HTTPS（profile=https 启用）
├── firewall.md      # 腾讯云安全组放行清单
└── README.md        # 腾讯云部署完整文档

docs/
├── onboarding.md    # 给下一个 AI / 接手者的入门
├── operations.md    # 生产运维 SOP（日常/升级/回滚/应急）
└── teacher-guide.md # 老师内测说明（含示例 prompt）

test/
├── cmm_test_v1_original.json     # CMM 数据集 56 条原题
├── cmm_test_v2_rewritten.json    # 改写后（明确作图指令）
└── 测试数据集.md

.github/ISSUE_TEMPLATE/  # bug-report + feature-request

CHANGELOG.md
docker-compose.yml
```

## License

MIT

---

## 接手 / 续作指南

**新一轮对话开始时**，请先读 [`docs/onboarding.md`](docs/onboarding.md)（给下一个 AI 或接手者的入门文档），
再看 [`CHANGELOG.md`](CHANGELOG.md) 顶部最新里程碑块，了解当前状态。

每次完成变更后，需要在 `CHANGELOG.md` **顶部**追加新版本块以保持一致性。
