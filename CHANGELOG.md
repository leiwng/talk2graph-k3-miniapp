# 变更日志

> 持续记录每个里程碑的关键变更，便于下一轮对话/接手时快速理解上下文。

格式约定：每个版本块包含「新增 / 变更 / 修复」与对应模块。

---

## W8 — 生产部署（当前版本）

**测试状态**：78/78 通过（W7 基础 +2 拒绝消息分类测试）

**目标**：将话图 T2G 真实部署到腾讯云轻量应用服务器，对外可访问，老师可以打开浏览器试用。

### 新增

**后端 — 拒绝消息分类增强（试用反馈即时迭代）**
- `app/api/chat.py::_make_refuse_message`：新增 `keywords_for_transform` 分支（旋转 / 平移 / 翻折 / 对称 / 镜像 / 变换 / 折叠）
  - 触发场景：老师输入"三角形旋转 180 度"等几何变换指令
  - 旧行为：落入通用拒绝消息，没有变通建议
  - 新行为：明确说明"几何变换在 V2 支持"，并给出 3 类替代描述方式（中心对称用 midpoint、轴对称用 foot_of_perp、旋转用对应边角等长等角）
- `app/llm/prompts/system.txt`：第 9 条把"几何变换"显式列入不支持类别，并给出 2 个 `{"error": ...}` 示例，引导 LLM 给出更精确的 reason
- `tests/test_w7_feedback.py`：+2 测试（`test_refuse_message_transform_rotate`、`test_refuse_message_transform_reflect`）

**部署 / 运维**
- `deploy/firewall.md`：腾讯云安全组放行清单（22/8080/443），含 nc/curl 验证命令、轻量"防火墙" vs CVM"安全组"差异说明
- `docs/operations.md`：生产运维 SOP —— 每日 10 分钟例行、滚动升级、代码/数据回滚、DB schema 变更流程、LLM Key 轮换、应急动作表、关键文件清单
- `docker-compose.yml`：caddy 通过 `profiles: [https]` 启用，平时不启动；`docker compose --profile https up -d` 一行切换

**文档**
- `README.md`：顶部"在线试用"占位、进度表加 W8、生产部署节加端口参数化用法
- `docs/onboarding.md`：当前里程碑 → W8

### 变更

- `docker-compose.yml`：`frontend.ports` 改为 `"${T2G_HOST_PORT:-8080}:80"`（默认 8080 避开 ICP 备案，可参数化）
- `deploy/bootstrap.sh`：
  - 支持 `T2G_HOST_PORT` 环境变量，默认 8080
  - **幂等**：检测到现有 DB 不再重建；显式 `T2G_RESET_DB=1` 才会重置（且先备份到 `data/backups/pre-reset-*.db`）
  - 健康检查走宿主端口
  - 自动安装 Docker 时提示"首次安装需重新 SSH"
  - 失败时 .env 缺失给出明确的火山 Provider 提示
- `deploy/backup-db.sh`：
  - `T2G_COS_BUCKET` 默认值 `cos://talk2graph-1259138134`（广州地域）
  - 检查 `sqlite3` 与 `coscli` 是否安装，未装时给出具体命令而不是干报错
- `deploy/README.md`：完整重写
  - 加"凭据安全"专章（防 LLM 对话泄露重演）
  - 明确说明"COS ≠ 服务器"（防再次混淆）
  - 端口/备案策略表（8080 vs 80 vs 443）
  - 火山方舟同区建议（北京）
  - HTTPS 切换文档化（profile=https）
  - 故障表 + 升级回滚指引同步到 `docs/operations.md`
- `backend/Dockerfile`：删除 `ENV DEFAULT_PROVIDER=zhipu`（让 `.env` 决定，避免镜像写死 default）

### 修复

- 之前 `deploy/bootstrap.sh` 隐含可能误删开发期 DB 的风险 → 现强制 opt-in
- `deploy/bootstrap.sh` 的 `git pull --ff-only || true` 会**静默吞掉**未配 origin / 网络失败等错误，导致"假成功"（镜像全 CACHED，容器 Running，但代码并没更新）→ 改为：
  - 先检查 `git remote get-url origin`，未配置时明确告警
  - 用 `git fetch origin main` + `git reset --hard origin/main`（仅当本地无未提交改动时），失败默认 exit 1
  - 提供 `T2G_SKIP_GIT=1` 逃生口，仅对当前本地代码重建（用于本机调试 / 网络故障时）

### 待落地（SSH 阶段后填回）

部署执行人完成 B 阶段后请回填以下信息到本块：
- [ ] 公网 IP：`http://_____:8080`
- [ ] 部署完成日期：____-__-__
- [ ] 火山方舟 endpoint：glm-5.2 / ep-______
- [ ] COS 备份首日验证日期：____-__-__（`coscli ls cos://talk2graph-1259138134/db/` 已见产物）
- [ ] 同步更新 `README.md` 顶部"在线试用"链接
- [ ] 同步更新 `docs/teacher-guide.md` 末尾访问入口
- [ ] 同步更新 `docs/operations.md` 第 9 节联系人

### DB Schema 升级

W7 → W8：**无 schema 变更**。直接 `./deploy/bootstrap.sh` 即可，DB 文件保留不动。

---

## W7 — 试用前发布打磨

**测试状态**：76/76 通过（W1 5 + W2 9 + W3 12 + W5 9 + W6-stress 20 + W6-ops 10 + W7 11）

### 新增

**后端**
- `app/db/models.py`：新增 `Feedback` 表（`session_id, snapshot_seq, rating, comment, nl, dsl_json, llm_provider, created_at`）
- `app/db/models.py`：`Message` 表新增 `error_kind` 列（`refuse / solve / patch / network / null`）
- `app/session/repo.py`：`add_feedback` / `list_feedback`
- `app/api/session.py`：`POST /api/session/{sid}/feedback`
- `app/api/admin.py`：
  - `GET /api/admin/feedback?days=N` — JSON 列表
  - `GET /api/admin/feedback.jsonl?days=N` — 下载导出
- `app/api/chat.py`：`_make_refuse_message(raw)` — LLM 拒绝原因转产品话术（按关键词识别函数图像 / 抛物线 / 立体 / 统计图 / 坐标）
- `app/llm/prompts/system.txt`：补充拒绝场景示例（5 类）
- `tests/test_w7_feedback.py`：11 个测试

**前端**
- `src/api/types.ts`：`Message.error_kind` / `Message.pending` / `ChatResult.error_kind` / `ChatResult.raw_reason`
- `src/api/client.ts`：`sendFeedback(sid, rating, comment?)`
- `src/store/index.ts`：
  - **乐观更新**：`sendChat` 立刻 push 用户气泡 + 「话图正在思考中…」占位
  - `sendFeedback` action
- `src/components/ChatPanel.tsx`：按 `error_kind` 渲染气泡颜色 + 思考占位（CSS 动画）
- `src/components/Canvas.tsx`：`<FeedbackOverlay />` 右下角 👍/👎 按钮（点 👎 弹输入框）
- `src/styles.css`：`.refuse` / `.solve-error` / `.thinking` / `.feedback-overlay` 样式

### 变更

- `app/api/chat.py`：失败路径全部记录 `error_kind`；refuse 时返回 `{ok:false, error_kind:"refuse", error, raw_reason, provider}`
- `app/api/session.py::list_messages`：返回值新增 `error_kind`
- `tests/test_w3_api.py`：`test_api_providers` 改为不硬编码 default 是 zhipu
- `app/llm/router.py` / `LLMRouter`：增加 MiniMax provider 注册
- `app/llm/base.py`：`OpenAICompatProvider.supports_json_mode` 类属性，默认 True
- `app/llm/volcengine.py`：`supports_json_mode = False`（火山 coding endpoint 不支持 json_object）
- `app/llm/{zhipu,volcengine,deepseek,minimax}.py`：base_url / model 全部支持环境变量覆盖
- `backend/.env.example`：完整改写，含场景示例

### DB Schema 升级

从 W6 → W7 升级需要：
```bash
# 开发期：删 DB 让 init_db() 重建
rm backend/data/talk2graph.db
```

生产期升级需手动 ALTER TABLE 或上 Alembic（当前未配置）。

---

## W6 — 内测打磨 + Docker 部署

### 新增
- 错误分类层 `app/api/errors.py`：把 LLM/Solver/Patch/DSL 错误归一为中文友好消息
- 20 题压测 `tests/test_w6_stress.py`
- Admin 用量统计 `GET /api/admin/stats?days=N`
- `backend/Dockerfile`、`frontend/Dockerfile`（nginx 多阶段）、`docker-compose.yml`
- 部署脚本 `deploy/bootstrap.sh` + 备份脚本 `deploy/backup-db.sh` + `Caddyfile`
- 老师手册 `docs/teacher-guide.md` + GitHub Issue 模板

### 变更
- 求解器默认 restarts 8 → 20（解决偶发不收敛）

---

## W5 — 扩展约束 + 渲染装饰 + 交互

### 新增（5 类约束）
- `midpoint{m,a,b}` / `foot_of_perp{f,p,a,b}` / `angle_bisector{a,b,c,d}` / `concyclic{points:[...]}` / `parallelogram{polygon}`

### 渲染装饰（按约束自动绘制）
- 直角小方块（`right_triangle` / `perpendicular`）
- 等长刻度（`equal_length` / `equilateral` / `isoceles`，1/2/3 道分组）
- 角度弧（`angle` 非 90° 时绘制）

### 前端交互
- 画板 hover 高亮 + tooltip（点坐标 / 线段长 / 圆半径）
- 画板拖动点（产生 `hint` 软约束 → 后端重解）
- SVG 根节点嵌入 `data-t2g-scale/offset/bbox/canvas-size` 供前端做客户端 → 数学坐标的逆变换

### 求解器
- `hint` 软约束：拖动产生的目标位置以低权重（0.05）加入残差

---

## W4 — 前端 MVP

- Vite + React 18 + TS + Zustand
- 三栏布局（对话 / 画板 / 对象树+属性）
- TopBar / ChatPanel / Canvas / RightPanel / ProviderSwitch 5 大组件
- 免登录：localStorage 持久化 `current_session_id` / `sessions[]` / `provider`
- 导出菜单：SVG / PNG / PDF / 剪贴板

---

## W3 — DSL diff + 会话 + API

### 新增
- `app/dsl/diff.py`：JSON Patch 子集（add/remove/replace）
- `app/db/`：SQLAlchemy async + aiosqlite；`session` / `message` / `dsl_snapshot` 表
- `app/session/repo.py`：会话 CRUD + push_snapshot + undo/redo + 截断分支语义
- `app/api/`：FastAPI 入口 + session/chat/export/providers 路由
- `app/config.py`：dotenv + 自动建 data/logs 目录
- `app/logging_setup.py`：structlog JSON + 按天滚动

### 测试
- `tests/test_w3_api.py`：12 个测试覆盖 patch / 仓库 / API 端到端

---

## W2 — LLM 抽象层 + Prompt

### 新增
- `app/llm/base.py`：`OpenAICompatProvider` 基类 + JSON 容错解析
- `app/llm/{zhipu,volcengine,deepseek}.py`：3 个 Provider 实现（后续 W7 加 MiniMax）
- `app/llm/mock.py`：离线测试用 MockProvider
- `app/llm/prompts/system.txt` + `fewshots.jsonl`（10+ 中文 few-shot）
- `app/llm/prompts/repair.txt`：校验失败时的修复提示
- `app/llm/extractor.py`：`extract_dsl()` — NL → DSL/patch，含 repair 循环
- `app/llm/router.py`：Provider 注册 + 默认 + 降级链

### 测试
- 9 个测试覆盖消息组装 / 抽取 / 代码块解包 / repair 循环 / patch 模式 / few-shot 校验

---

## W1 — DSL + 求解器 + SVG 渲染

### 新增
- `app/dsl/schema.py`：Pydantic v2 几何 DSL（v0.1）
- `app/dsl/validator.py`：引用完整性 + 语义校验
- `app/solver/engine.py`：scipy.least_squares + gauge fixing + 多初值重启
- `app/render/svg.py`：SVG 输出（点/线/圆/多边形 + 中文标签 + 长度/角度/半径标注）
- `tests/test_w1_endtoend.py`：5 个 golden case

### 已支持约束
长度 / 等长 / 角度 / 平行 / 垂直 / 共线 / 相切 / 点在圆上 / 等腰 / 等边 / 直角三角形 / 半径

---

## 数据集

| 文件 | 内容 |
|---|---|
| `test/cmm_test_v1_original.json` | 56 条原题（含 LaTeX 公式） |
| `test/cmm_test_v2_rewritten.json` | 56 条改写后（明确作图指令；48 done + 8 skipped）|
| `test/测试数据集.md` | 早期 38 题测试集（已不在 results 中）|

评估脚本：
- `backend/scripts/eval_cmm.py v1 / v2r / both`
- `backend/scripts/rewrite_v2.py` — 用 LLM 把 v1 原题改写成 v2r
- `backend/scripts/compare_v1_v2r.py` — 生成 A/B 对比报告

最近一次评估（火山 GLM-5.2）：
- v1 原题：39/56 (69.6%)
- v2r 改写：38/56 (67.9%)
- 改写后 LLM 拒绝率从 30% 降至 16%

---

## 关键架构决策

1. **几何精度** ≠ 0：求解器是 scipy.least_squares，残差通常 < 1e-15（机器精度）；不用 SymPy 符号求解（V2 计划）。
2. **DSL 不含坐标**：LLM 只输出对象 + 约束，坐标由求解器算出。这是几何严谨性的核心保证。
3. **多 Provider 抽象**：所有 Provider 走 OpenAI 兼容 endpoint；不同模型支持 `response_format=json_object` 与否由 `supports_json_mode` 控制。
4. **错误分级**：
   - `refuse`（LLM 主动拒绝，超出 MVP 范围）→ 黄色友好气泡，不打扰
   - `solve` / `patch`（求解或修改失败）→ 紫色提示
   - `network`（鉴权/限流/网络）→ 红色顶部条
5. **数据持久化**：所有老师 NL、AI 回复、反馈都进 SQLite，便于后续分析、改 prompt、训练专属模型。

## 下一步路线图（建议优先级）

### 即将做
1. **真去腾讯云部署** + 申请 HTTPS 域名
2. **5-10 位老师定向试用**，收 👍/👎 数据
3. **SSE 流式输出**（替代当前阻塞式）
4. **历史会话侧抽屉**

### V2（1-2 个月）
5. **坐标系支持**：扩 DSL 增加 `axis` / `grid` 对象
6. **函数图像**：独立采样渲染路径（不走约束求解）
7. **PPT 字体 outline 化**：解决导出兼容
8. **求解器加速**：对常见模式做符号求解

### V3（长期）
9. 立体几何（three.js + 投影到 SVG）
10. 统计图表（独立模块）
11. WPS / Office 插件
