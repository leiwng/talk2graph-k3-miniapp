# 给下一个 AI（或接手者）的话

> **如果你是新一轮对话的 AI 助手，从这里开始。**

## 5 步入门

### 1. 读上下文（按顺序）

```
CHANGELOG.md      # 顶部即最新状态：当前里程碑、变更点、DB schema、路线图
README.md         # 项目结构、进度表、快速上手
```

完成后你应能回答：
- 当前是哪个 W 字头里程碑？
- 累计多少个测试？
- 默认 LLM Provider 是什么？
- 哪些题型在 MVP 范围 / 哪些不在？

### 2. 验证环境

```bash
cd backend
.venv/bin/pytest -q
```

预期：与 CHANGELOG 顶部记录的测试数一致（V2-F.2 = 219 个）。如不一致：
- 测试**失败** → 报告失败项，**不要随意修复**，等用户指示
- 测试**数变少** → 可能新代码丢了测试，对照 CHANGELOG 排查
- 测试**数变多** → 上次对话有人忘了更新 CHANGELOG

### 3. 看后端是否在跑

```bash
pgrep -fl uvicorn
curl -s http://127.0.0.1:8000/api/health
```

如果在跑，**不要随意 kill**。如果要重启，**用户的终端启动的有 `--reload`**，让用户自己重启。

### 4. 看用户当前关注什么

通常用户会说一句话，比如"继续做 X" / "修一下 Y"。**不要急着开干**，先：
- 在 `CHANGELOG.md` 的"下一步路线图"看 X 是否已规划
- 如果是路线图里的事项，按约定的优先级和方案做
- 如果是新需求，**先用 Plan 模式**列变更点（涉及哪些文件、加多少代码、要不要改 schema），让用户确认

### 5. 完成变更后必做

- [ ] 跑全部测试 `pytest -q`
- [ ] 前端有改动则 `npm run build` 验证
- [ ] **在 `CHANGELOG.md` 顶部加新版本块**（新增/变更/修复 三栏）
- [ ] 如有 DB schema 变更：写明升级方法（开发期 `rm` DB，生产期手动 SQL）
- [ ] 让用户知道动了哪些文档（不仅是代码）

---

## 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| 后端报 LLM 网络错误 | uvicorn 在 .env 修改前就启动了，`--reload` 不重读 env | 重启 uvicorn |
| 火山 LLM 返回 400 `response_format.type` | coding/v3 endpoint 不支持 json_object | 已通过 `VolcengineProvider.supports_json_mode=False` 处理，不要回退 |
| 升级后旧会话打不开 | DB schema 变了 | 开发期删 `data/talk2graph.db` 让 init_db 重建 |
| LLM 拒绝抛物线 | 不是 bug，MVP 不支持圆锥曲线 | 看 system.txt 的拒绝示例 |
| 测试中 `default_provider` 不对 | env 影响 | `test_w3_api.py::test_api_providers` 只断言在三家之一 |

---

## 编码约定（沿用项目原有风格）

- 后端：Python 3.11，type hints，Pydantic v2，async 优先
- 前端：TS strict，Zustand store，函数式组件 + hooks
- 不要乱加文件——优先扩展已有模块
- 不要写无用的注释或文档块
- LLM 相关：永远不暴露 API Key 到对话里

---

## 紧急回退

如果发现刚改的东西破坏了什么：

```bash
git status              # 看动了哪些文件
git diff                # 看具体改动
git checkout -- <file>  # 回退某个文件
```

数据库回退：

```bash
rm backend/data/talk2graph.db
# 重启后端，init_db() 会按当前 models.py 重建
```

---

## 当前里程碑（手动更新此值，每次 W 完成后改）

**V2-F.2 — 付费 + 配额限流 + 安全加固**（2026-07-17 完成）

- 测试：219/219 通过（V2-F.1 205 + V2-F.2 14 新增）
- 目标：Alipay 电脑网站支付（沙箱）+ 配额限流（free 5/天 / pro 30/天）+ 强制登录 + API Key 泄露防护
- 关键设计：
  - **Alipay 电脑网站支付**：RSA2 签名 + 异步 webhook（幂等 + 月续期）；密钥文件挂载到容器 `/app/secrets/`
  - **配额限流**：free 5/天 / pro 30/天；按当日 snapshot 数计数（LLM 失败不扣配额）
  - **per-user 配额覆盖**：`UserSubscription.daily_graph_limit_override` 字段，admin 可 SQL 调整
  - **强制登录**：所有 session/chat/export 端点要求 Bearer token（删除匿名试用体验，防外部滥用）
  - **安全事件防护**：`.githooks/pre-commit` 阻止 sk-/ark- 开头 20+ 字符的 Key 被提交
- 后端：新增 `app/payment/`（plans/alipay/subscription/entitlement/repository）+ `app/api/payment.py` + `app/api/webhooks.py`；DB 加 3 张表
- 前端：PricingPage + SubscriptionPage + api/payment.ts；路由加 `/pricing` + `/account/subscription`
- 安全：`.githooks/pre-commit` + `docs/security.md` + `.gitignore` 加 `model_config*.md`
- 既有改造：session/chat/export 路由强制登录；admin 端点加 `require_admin`
- LLM：火山方舟 GLM-5.2
- DB schema：新增 3 张表；不删现有 DB，`create_all` 自动建；现有 DB 的 plan 配额需手动 SQL 更新
- 配置：新增 6 个 Alipay env（`ALIPAY_APP_ID` / `ALIPAY_APP_PRIVATE_KEY_FILE` / `ALIPAY_PUBLIC_KEY_FILE` / `ALIPAY_NOTIFY_URL` / `ALIPAY_RETURN_URL` / `ALIPAY_GATEWAY_URL`）
- 不含：邮箱验证码（F.3）/ WeChat OAuth（F.3）
- 下一步候选：V2-F.3（邮箱验证码 + WeChat OAuth + SMTP）/ Alipay 正式应用上线后切正式环境 / admin 管理界面

---

## 历史里程碑

**V2-F.1 - 用户体系 + 审计骨架**（2026-07-07 完成）

- 测试：205/205 通过（V2-E 173 + V2-F.1 32 新增）
- 目标：邮箱+密码注册/登录、JWT + auth_version 失效机制、审计日志（含每次 chat 作图）、Session 归属校验、Admin 权限保护、前端路由 + 登录页
- 关键设计：
  - **JWT in localStorage** + `auth_version` claim：改密后 `password_changed_at` 更新 -> 旧 token 立即失效（无 token 黑名单）
  - **匿名会话保留试用体验**（F.2 后取消）：未登录仍可用，归属内置 anonymous 用户；登录用户只能访问自己的 session（cross-user 404 防探测）
  - **审计 best-effort**：所有写入 try/except + logger.warning，永不阻塞主流程；chat.send 走 `asyncio.create_task` fire-and-forget
  - **Bootstrap admin**：首次启动按 env 创建管理员（账号创建后 env 可删除）
- 后端：新增 `app/auth/`（password/jwt_token/deps/repository）+ `app/audit/`（actions/repository）+ `app/api/auth.py` + `app/api/audit_log.py`；DB 加 2 张表（user / audit_log），session 加 user_id 列（ensure_schema 自动 ALTER）
- 前端：引入 `react-router-dom`，路由结构 `/ /login /register /forgot-password /app（守卫）/account（守卫）/account/password（守卫）`；AuthStore 独立；LoginPage / RegisterPage / ForgotPasswordPage / AccountPage / ChangePasswordPage 5 个页面；TopBar 加 UserMenu
- 既有改造：admin 端点全部加 `Depends(require_admin)`；session API 加归属校验
- 测试既有改造：test_w6_ops.py + test_w7_feedback.py 加 admin token fixture
- LLM：火山方舟 GLM-5.2
- DB schema：新增 2 张表 + session.user_id 列；开发期 `rm backend/data/talk2graph.db` 重建，生产期启动自动迁移
- 配置：新增 3 个 env（`T2G_JWT_SECRET` / `T2G_BOOTSTRAP_ADMIN_EMAIL` / `T2G_BOOTSTRAP_ADMIN_PASSWORD`）
- 下一步候选：~~V2-F.2（付费 + 配额）~~ 已完成 / V2-F.3（邮箱验证码 + WeChat OAuth）/ 历史会话侧抽屉

---

## 历史里程碑

**V2-E — 多 Provider 评测 + UI/UX 打磨 + 自动 Fallback**（2026-07-07 完成）

- 测试：162/162 通过（W13-B.1 151 + V2-C 11）
- 新增能力：导出 SVG/PNG/PDF 时把 `<text>` 元素转为 `<path>` 矢量 outline
  - 解决复制到 PPT 后中文/特殊符号字体丢失问题
  - 新增 `app/render/text_to_path.py`：fonttools 提取字形 outline
  - 内置 Source Han Sans SC 子集字体（90MB → 28KB）
  - 浏览器预览仍用 `<text>`（性能好、可交互）；导出强制 outline
- LLM：火山方舟 GLM-5.2
- 无 DB schema 变更
- 下一步候选：求解器符号求解加速（V2 #8）/ 老师试用反馈 / SSE 流式

---

## 历史里程碑

**W13-B.1 — Provider 配置修补**（2026-07-06 完成）

- 测试：151/151 通过（W13-B 149 + W13-B.1 修补 2）
- 新增能力：
  - **W13-A（v0.13.0）**：求解器自适应重启（stage-2 抢救 + 4 种初值策略），成都真题通过率 60.3% → 70.6%
  - **W13-B（v0.13.1）**：solve_repair 回路 + 约束诊断 + prompt 处理歧义，成都真题符合预期率 61.8% → 76.5%
  - **W13-B.1（修补）**：kimi 网络错误 hint 按 provider 动态生成域名；doubao 降级到 Seed-2.0-pro；kimi-k2.6 关闭 thinking 避免超时
  - SolveError 携带 residual + worst_constraint 诊断字段
  - Solve 残差 > 1e-2 时自动请 LLM 修正 DSL 再求解
- LLM：火山方舟 GLM-5.2
- 成都真题（68 题）综合成绩：
  - **48/68 (70.6%) 通过、52/68 (76.5%) 符合预期**
  - 平均延迟 26s，平均残差 1e-6（几何精确）
- 无 DB schema 变更
- 下一步候选：老师试用反馈 / 多 Provider 对比 / 回归黑盒测试 / SSE 流式

---

**W13-A — 求解器自适应重启**（2026-07-02 完成、v0.13.0 已 tag）

- 测试：145/145 通过（W12 141 + 4 W13）
- 新增能力：solver 阶段 2 抢救，restarts_extra=20 默认开启
  - 4 种初值策略：narrow / perturb_hint / wide / default
  - 收益条件触发（阶段 1 未完全成功时才启动）
- 成都真题：60.3% → 70.6% (+7 题)
- 10 题 solve_fail → ok 直接受益

---

**W12 — on_curve 硬约束 + 求解器 hint 残差分离**（2026-07-01 完成、v0.12.1 已 tag）

- 测试：141/141 通过（V2-B 134 + W12 7）
- 新增能力：`on_curve{point, curve}` 硬约束
  - LLM 可用 on_curve 强制点在函数曲线上，而不是只靠 hint 近似
  - 求解器权重 10，压制 hint 软约束的 0.05 拉扯
  - Solver hint 残差与硬约束残差分离，修复"hint 距离远误报未收敛"的潜在 bug
- LLM：火山方舟 GLM-5.2
- 成都真题评估：17/20 → **18/20 (90%)**
  - 椭圆题 gk_hard_02 refuse → ok：LLM 学会拆椭圆为两条 curve + on_curve
  - 反比例题 zk_med_03 DSL 输出升级，几何精度提升到 1e-7
- 无 DB schema 变更
- 下一步候选：老师试用反馈 / SSE 流式 / 历史会话侧抽屉 / PPT outline

---

## 历史里程碑

**V2-B — 函数图像**（2026-07-01 完成、v0.12.0 已 tag）

- 测试：134/134 通过（W11 115 + V2-B 19）
- 新增能力：函数图像 `y = f(x)` / `x = g(y)`
  - 一次/二次/反比例/正弦余弦/指对数 全部可画
  - 抛物线 `y²=2x` 拆成两条曲线 `y=±√(2x)` 支持
  - 关键新模块 `app/dsl/safe_expr.py`：AST 白名单沙箱，绝不 `eval(str)`
  - 渲染时断点切段（|y|>1000 或 nan/inf）保证 1/x 类曲线不飞出屏幕
- LLM：火山方舟 GLM-5.2（`.env` 默认）
- cmm v2r：36/56（vs W11 34/56，+2 题）
  - **V2-B 目标题 #6「抛物线 y²=2x 及其准线」refuse → ok**（打通）
  - **#16「反比例 y=k/x 与 y=x 的交点」refuse → ok**（直接收益）
  - #13 #17 LLM 又想通了，正向漂移
  - #21 #43 solve_fail、#53 refuse，LLM 输出漂移，非 V2-B 代码
- 无 DB schema 变更
- V2 主线完成

---

## 历史里程碑

**W11 — 几何变换**（2026-07-01 完成、v0.11.0 已 tag）

- 测试：115/115 通过（W10 103 - 2 W7 过时 + 14 W11）
- 新增能力：4 种变换（rotation / translation / reflection / central_symmetry）+ 派生对象机制
  - 派生对象不占求解自由变量，坐标由 `_apply_derived_objects` 后处理注入
  - Renderer 派生多边形虚线 + 派生顶点自动加撇（`A_p` → `A'`）
  - Validator 放宽：允许 segment/polygon 引用派生点

---

**W10 — 半平面约束 + patch fallback + DB 自动迁移**（2026-07-01 完成、腾讯云已上线）

- 测试：103/103 通过（W9 89 + W10 14）
- 部署：v0.10.0 已合入腾讯云 `49.233.15.73:8080`，本地 + 生产 3 句手测全过
- 新增能力：
  - 「C 在 AB 上方」类方位描述稳定输出（same_side / opposite_side 约束）
  - patch 不合法时自动 fallback 重画，前端灰色提示"已重新理解为重画"
  - DB schema 变更零运维（`ensure_schema()` 启动自动 ALTER TABLE 加列）
- 评估：cmm v2r 35/56（vs W9 36/56，仅 #48 LLM 拒绝更严谨，非回归）

---

**W9 — V2-A 坐标系支持**（2026-06-30 完成）

- 测试：89/89 通过
- DSL：新增 `AxisObj`，DSL 最多 1 个 axis
- Solver：有 axis 时 gauge 改为 "origin 固定 (0,0)、其他点全自由"
- Render：绘制网格 / 主轴 / 箭头 / 刻度 / 单位标签
- 拒绝改写：删 `keywords_for_coord`，新增 `keywords_for_coord_value`（仅 A(2,3) 类拒绝）

---

**W8 — 生产部署**（2026-06-26 完成）

- 测试：78/78 通过
- 部署：腾讯云轻量服务器 2C4G + Docker Compose；对外 `:8080`
- LLM：火山方舟 GLM-5.2 单 Provider
- 备份：COS `talk2graph-1259138134` (ap-guangzhou) 每日 3:00

---

**W7 — 试用前发布打磨**（2026-06-26 完成）

- 测试：76/76 通过
- DB：`message.error_kind` + `feedback` 表
- 前端：乐观更新 + 拒绝分色 + 反馈按钮

---

**最后一句**：用户重视**前后一致性**胜过速度。有疑问先问，别揣测；改动较大先 Plan 后 Build。
