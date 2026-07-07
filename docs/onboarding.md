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

预期：与 CHANGELOG 顶部记录的测试数一致（V2-D = 173 个）。如不一致：
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

**V2-D — SSE token-level 流式**（2026-07-06 完成）

- 测试：173/173 通过（V2-C 162 + V2-D 原 6 + V2-D token-level 流式 5）
- 目标：让 LLM 调用 8-17 秒阻塞期间不再只显示干等转圈，而是**实时推送 token 流 + 已识别对象列表**给前端，用户看到 "AI 正在生成：点 A / 线段 AB / 圆 O..."。stage 事件保留作为阶段切换标记。
- 关键发现：
  - CHANGELOG 之前版本块说"所有 stage 事件最后一次性打印"——经实测验证，**当前代码（带 `await asyncio.sleep(0)`）下其实早已不成立**：第一个 stage=llm 事件在 0.02s 流式到达，后续 stage 一起到是因为它们之间无真正阻塞操作（patch 是直接赋值、solve 通常 <1ms、render <10ms）
  - `--http h11 --loop asyncio` 跟默认 uvicorn 行为完全一致，不需要切换
  - 不需要上 sse-starlette 库（默认 StreamingResponse 已能流式）
  - 真正的"用户看不到流式"问题是 **LLM 阻塞期间没有 token 流**——本次升级解决
- 实测（curl + 真实 LLM，等边三角形）：
  - 0.03s STAGE#1 llm 流式到达
  - 4.77s 第一个 TOKEN 到达（GLM-5.2 首字延迟）
  - 4.97s-6.66s 7 个 OBJ 事件依次到达（A/B/C/AB/BC/CA/tri）
  - 8.17s DONE
  - 总计 40 token + 7 object_seen 事件
- 体验打磨（V2-D 收尾）：
  - 首字延迟期加"AI 正在准备输出..."次级提示（stage=llm 后 2s 没收到 token 触发，第一个 token 到达清除）
  - object_seen 用 requestAnimationFrame 批量 flush（每帧最多触发一次 React re-render，避免每秒 30+ token 卡顿）
  - stage 切换时不再清空对象列表（保留全程已识别对象）
  - 修复 thinking 气泡 raw 显示 `__stream__:{...}` 文本 bug（`slice(10)` off-by-one）
- LLM：火山方舟 GLM-5.2（coding/v3 endpoint 完全支持 stream=True）
- 无 DB schema 变更
- 下一步候选：老师试用反馈 / 多 Provider 对比 / 历史会话侧抽屉

---

## 历史里程碑

**V2-C — PPT 字体 outline 化**（2026-07-06 完成）

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
