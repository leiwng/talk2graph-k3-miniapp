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

预期：与 CHANGELOG 顶部记录的测试数一致（W12 = 141 个）。如不一致：
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
