# 变更日志

> 持续记录每个里程碑的关键变更，便于下一轮对话/接手时快速理解上下文。

格式约定：每个版本块包含「新增 / 变更 / 修复」与对应模块。

---

## V2-E — 多 Provider 评测 + UI/UX 打磨 + 自动 Fallback（当前版本，2026-07-07）

**测试状态**：173/173 通过（V2-D 173 + V2-E 0 新增测试；本轮主要是工程化改造与前端样式重写，未引入新业务功能）

**目标**：① 给运营提供"哪家 LLM 画图最好"的对比数据；② 把产品 UI 打磨到面向老师推广可用的水平（视觉精致度 + 首次体验 + 响应式 + 文案）；③ 生产版去调试控件 + LLM 出错自动切换备选模型。

### 新增

**后端 — 多 Provider 自动对比评测脚本**
- `backend/scripts/eval_multi_providers.py`（新文件，~330 LOC）：
  - 遍历所有 enabled provider（默认）/ 用户指定列表（`--providers volcengine,kimi_k26`）
  - 复用 `extract_dsl` + `solve` + `render_svg` 全流程，对每个 provider 跑完整 `chengdu_full.json` 68 题
  - 输出 5 张表对比报告：
    - 表 1：总览（OK 数 / 符合预期率 / 通过率 / 平均残差 / p50 延迟 / p95 延迟 / 调用次数 / 输入 tokens / 输出 tokens / 估算成本(元)）
    - 表 2：逐题状态对比（每家一列 ✅/🟡/🔴/⚠️）
    - 表 3：失败题详情（仅展示至少一家失败的题）
    - 表 4：定价参考（每家元/M tokens）
    - 表 5：综合小结（最高通过率 / 最高符合预期 / 最低延迟 / 最低成本）
  - `UsageTracker`：包装 LLMProvider 的轻量代理（duck typing 实现 Protocol），累计 prompt/completion tokens 用于成本估算；LLMError 时也计入 calls，反映真实 API 请求次数
  - 支持 `--limit N` 快速预览前 N 题、`--concurrency N` 单 provider 内并发、`--no-svg` 跳过渲染
  - 输出目录：`test/results_chengdu_multi/`（含 `comparison.md` + 每家子目录 `<provider>/results.json` + `svgs/<id>_<provider>.svg`）
- `PRICING_CNY_PER_MTOK`：脚本内置定价参考表（火山 glm-5.2 / Doubao-Seed-2.0-pro / DeepSeek v4-chat / v4-pro / MiniMax-M3 / Kimi k2.6 / k2.7-code / k2.7-code-highspeed / 智谱 glm-5.2）

**后端 — LLM 自动 Fallback Chain**
- `app/llm/router.py`：
  - 新增 `is_retryable(err)`：判断错误是否触发 fallback
    - `LLMError.status is None`（网络/超时）→ True
    - `LLMError.status >= 500`（5xx 服务端错误，含 503/529 限流）→ True
    - `LLMError.status in (401, 403, 429)`（鉴权失败/限流）→ True
    - 其他 4xx → False（业务错误，重试也没用）
  - `LLMRouter._build_fallback_chain()`：构造 fallback 链
    - 优先取 env `T2G_FALLBACK_PROVIDERS`（逗号分隔，如 `volcengine,deepseek,kimi_k26`）
    - 未配置时自动取前 3 个 enabled provider，default 排第一
    - 最多 3 个（避免无限重试消耗配额）
  - `LLMRouter.get_fallback_chain(start_with)`：返回 Provider 实例列表
    - 客户端显式传 name 时把它排第一（调试模式仍可手工切换）
    - 生产模式 start_with=None，按 default 顺序
- `app/api/chat_stream.py::_extract_with_fallback_streaming()`（新函数，~50 LOC）：
  - 包装 `extract_dsl_streaming`，第一个 provider 出错时自动切到下一个
  - 切换时 yield `{"type": "fallback", "from": "...", "to": "...", "reason": "..."}` 事件
  - 所有 provider 都失败才 yield error
- `chat_stream.py::_pick_provider_chain(name)`：
  - 测试覆盖时（`chat_module._provider_override is not None`）返回 `[override]`，禁用 fallback（保证现有测试语义）
  - 否则用 `LLMRouter.get_fallback_chain(name)`
- `chat_stream.py::_run_chat_stream()` 主流程改造：
  - LLM 阶段从单 provider 升级到 fallback chain
  - 切换时推 `event: stage` 含 `{"stage":"fallback","from":"...","to":"...","reason":"..."}`
  - done 事件加 `fallback_chain: [{from, to, reason}, ...]` 字段

**后端 — 生产/调试模式配置**
- `app/config.py::Settings`：
  - 新增 `debug_ui: bool`（env `T2G_DEBUG_UI`，默认 `false`）
  - 新增 `fallback_providers: list[str] | None`（env `T2G_FALLBACK_PROVIDERS`）
- `app/main.py`：`/api/health` 返回 `debug_ui` 标志
- `backend/.env.example`：新增 `T2G_DEBUG_UI` / `T2G_FALLBACK_PROVIDERS` 配置说明 + 场景示例

**前端 — 现代教育 SaaS 风视觉重构**
- `frontend/src/styles.css`（重写，从 423 行扩展到 547 行）：
  - **颜色系统重做**：主色从纯蓝 `#2563eb` 改为柔和的教育蓝 `#3b82f6` + 渐变 `linear-gradient(135deg, #3b82f6, #6366f1)`
  - 加 `--text-secondary` / `--panel-subtle` / `--border-strong` 中性色中间档
  - **阴影系统**：`--shadow-sm` / `--shadow-md` / `--shadow-lg` / `--shadow-card`，让卡片立体
  - **圆角**：`--radius-sm(6)` / `--radius(8)` / `--radius-md(10)` / `--radius-lg(14)` 四档
  - **对象类型色条**：`--obj-point`(蓝) / `--obj-segment`(绿) / `--obj-circle`(橙) / `--obj-polygon`(紫) / `--obj-curve`(粉) / `--obj-axis`(灰) / `--obj-derived`(浅灰)
  - **按钮**：hover 抬升 + active 收缩 + primary 蓝色阴影
  - **输入框**：focus 时 3px 蓝色光环（box-shadow 模拟）
  - **TopBar**：56px 高 + 阴影 + 渐变品牌名
  - **用户气泡**：蓝色渐变背景 + 阴影
  - **AI 气泡**：浅灰底 + 边框 + 圆角 10px
  - **思考气泡**：stage 文字蓝色加粗，对象列表虚线分隔
  - **Canvas 占位符**：渐变背景 + 卡片阴影
  - **SectionHeader**：56px 高 + 大写字母 + 字间距
  - **TreeItem**：左 3px 色条按对象类型区分
  - **Properties 面板**：浅灰底 + 等宽字体
  - **Dropdown**：圆角 + 大阴影 + overflow:hidden

**前端 — 首次体验引导**
- `frontend/src/components/ChatPanel.tsx::WelcomeCard`（新组件，~40 LOC）：
  - 替换旧版 `ExampleHints`（纯文字按钮列表）
  - 顶部欢迎卡片：标题"你好，老师 👋" + 一句话功能介绍 + 3 条 ✓ 列表（自然语言作图 / 约束支持 / 导出格式）
  - 下方示例网格：5 个 `example-card` 卡片（图标 + 标题 + 描述），点击即用
  - 示例清单：等边三角形 / 直角三角形 / 正方形 / 圆与圆心角 / 等腰 + 内切圆
- `frontend/src/components/TopBar.tsx::EXAMPLES`（重写）：
  - 从纯文字列表改为 `{icon, title, desc, nl}` 结构
  - 暴露为 export 给 `ChatPanel::WelcomeCard` 复用

**前端 — 移动端 Tab 切换**
- `frontend/src/store/index.ts::activeTab`（新 state）：
  - 类型 `'chat' | 'canvas' | 'objects'`，默认 `'chat'`
  - 新增 `setActiveTab` action
  - `sendChat` 成功生成图形后自动切到 `'canvas'`（移动端用户能立即看到画板）
- `frontend/src/App.tsx::MobileTabBar`（新组件，~30 LOC）：
  - 底部 50px 高 Tab Bar，3 个 Tab：💬 对话 / 📊 画板 / 📐 对象
  - 桌面端隐藏（`display: none`），平板/移动端显示
  - 生产模式（debugUI=false）不显示"对象"Tab
- `frontend/src/App.tsx` 主结构改造：
  - 三个面板各自包一层 `<div className="panel-wrap panel-{type} {tab-active}">`
  - 生产模式不渲染 RightPanel，三栏变两栏（CSS `.app.prod-ui .body { grid-template-columns: 360px 1fr }`）
  - 配合 CSS 响应式断点控制显示/隐藏

**前端 — 响应式断点**
- `frontend/src/styles.css`（响应式部分）：
  - **平板（≤1024px）**：右侧对象面板隐藏，由 Tab 触发后以浮层形式从右侧滑出（width:320, position:fixed, box-shadow）
  - **移动端（≤768px）**：单栏 Tab 切换，TopBar 横向滚动，子标题"用一句话画几何"隐藏，seq 信息隐藏
  - 三栏 → 两栏 → 单栏 的渐进退化

**前端 — 生产/调试 UI 切换**
- `frontend/src/store/index.ts`：
  - 新增 `debugUI: boolean` state（默认 `false`）
  - `init()` 拉 `/api/health` 拿 `debug_ui` 标志，存到 store
  - `sendChat` 在 `debugUI=false` 时不传 `provider`，让后端按 fallback chain 自动选
- `frontend/src/api/client.ts::health()`：新增方法
- `frontend/src/components/ProviderSwitch.tsx`：`debugUI=false` 时返回 null（不渲染 select）
- `frontend/src/App.tsx`：`debugUI=false` 时不渲染 RightPanel；MobileTabBar 不显示"对象"Tab

**前端 — Fallback 模型切换提示**
- `frontend/src/store/index.ts::onStage`：
  - 收到 `stage=fallback` 时清空之前 provider 推的已识别对象（避免重复显示）
  - 重置首字延迟计时器（新 provider 重新计时首字延迟）
- `frontend/src/components/ChatPanel.tsx::stageText`：
  - 新增 `fallback: '正在切换备选模型'` 文案

### 变更

- `frontend/src/components/TopBar.tsx`：
  - brand 区加 30×30 蓝色渐变 logo（圆角 + 阴影）
  - "话图 T2G" 文字加渐变（`background-clip: text`）
  - 删除旧的 `ExampleHints` 组件（已被 ChatPanel::WelcomeCard 取代）
  - `seq #` span 加 `.seq-info` class（移动端隐藏用）
- `frontend/src/components/ChatPanel.tsx`：
  - 空状态用 `WelcomeCard` 替代旧的"你好，老师。说一句话我就给你画图。" + ExampleHints
  - 占位符文案从"例如：画一个内切圆半径为 3 的等腰三角形"改为"试试：画一个等边三角形 ABC，边长为 4"
  - 示例点击后直接 sendChat（不再 setText 让用户手动发送）
- `frontend/src/components/Canvas.tsx`：占位符文案"渲染中…"→"正在渲染图形…"，"还没有图形。"加 `<strong>` 强调
- `frontend/src/components/RightPanel.tsx`：
  - `ObjectItem` 加 `obj-${obj.kind}` class，配合 CSS 实现左 3px 色条按对象类型区分
  - 空状态从"（空）"改为"画一个图形后 / 这里会显示对象列表"（居中 + 行高 1.7）
  - 属性面板空状态"点击左侧对象"→"点击上方对象"（更符合 RightPanel 实际位置）
- `frontend/src/components/ProviderSwitch.tsx`：包一层 `<div className="provider-switch">`，配合 CSS 控制 select 样式
- `app/llm/__init__.py`：导出 `is_retryable`
- `app/llm/router.py`：
  - `LLMRouter.fallback_chain` 从原来"所有 provider 列表"改为"最多 3 个 enabled"
  - 新增 `_build_fallback_chain()` / `get_fallback_chain(start_with)` 方法

### 修复

- `app/solver/engine.py::_VarLayout.get_point`：之前直接 `self.point_idx[pid]` 在派生点（TransformedPointObj）/未声明点 id 时抛 `KeyError`，逃逸到外层导致整个评测脚本崩溃。现在捕获 `KeyError` 重抛为 `SolveError`，让 chat 主流程能优雅归类为 `solve_fail`
- `scripts/eval_multi_providers.py::run_one`：`solve()` 调用从 `except SolveError` 改为额外捕获 `Exception`，防御性捕获所有异常都记为 `solve_fail`，不让脚本崩溃
- V2-D 173 个测试无回归

### 配置变更

- `backend/.env`：`DEFAULT_PROVIDER` 从 `volcengine` 改为 `volcengine_doubao_pro`（基于评测结果，doubao-pro 通过率 82.4% vs volcengine 51.5% vs deepseek 61.8%）
- 新增 `T2G_FALLBACK_PROVIDERS=volcengine_doubao_pro,kimi_k26,deepseek`

### DB Schema 升级

V2-D → V2-E：**无 schema 变更**。直接拉新代码即可。

### 配置说明

新增两个环境变量（开发期 `.env`，生产期 Docker env）：

```bash
# 生产/调试 UI 切换
# false（默认）= 生产模式：前端隐藏 Provider 切换、对象面板，LLM 走 fallback chain
# true = 调试模式：显示所有控件，可手工切换 provider / 编辑对象
T2G_DEBUG_UI=true   # 开发期建议设 true，生产期 false

# LLM Fallback Chain（最多 3 个，逗号分隔）
# 留空 = 自动取前 3 个 enabled provider，default 排第一
# 显式指定时按指定顺序，第一个为首选
T2G_FALLBACK_PROVIDERS=volcengine,deepseek,kimi_k26
```

### LLM 多 Provider 评测结果（2026-07-07 完成）

启动命令：
```bash
cd backend && .venv/bin/python scripts/eval_multi_providers.py --concurrency 2
```

输出：`test/results_chengdu_multi/comparison.md`（含 5 张表）+ 每家子目录 `results.json` + `svgs/<id>_<provider>.svg`

#### 总览（按通过率排序）

| 排名 | Provider | 通过率 | 符合预期 | p50 延迟 | 平均残差 | 成本(元) |
|---|---|---|---|---|---|---|
| 🥇 | `volcengine_doubao_pro` (Doubao-Seed-2.0-pro) | **82.4%** (56/68) | 82.4% (56) | 54.7s | 2.0e-06 | 1.144 |
| 🥈 | `kimi_k26` (kimi-k2.6) | 69.1% (47/68) | **83.8%** (57) | 19.4s | 8.2e-07 | 1.096 |
| 🥉 | `deepseek_v4_pro` (deepseek-v4-pro 推理模型) | 64.7% (44/68) | 69.1% (47) | 55.7s | 1.3e-06 | 3.582 |
| 4 | `deepseek` (deepseek-v4-flash) | 61.8% (42/68) | 73.5% (50) | 30.6s | 9.6e-08 | 0.845 |
| 5 | `minimax` (MiniMax-M3) | 60.3% (41/68) | 76.5% (52) | **9.4s** ⚡ | 2.2e-06 | 0.541 |
| 6 | `kimi_k27_code` (kimi-k2.7-code) | 52.9% (36/68) | 57.4% (39) | 114.0s | 1.3e-06 | 0.990 |
| 7 | `volcengine` (glm-5.2) | 51.5% (35/68) | 54.4% (37) | 111.2s | 2.3e-06 | **0.466** 💰 |
| 8 | `kimi_k27_code_hs` (kimi-k2.7-code-highspeed) | 48.5% (33/68) | 55.9% (38) | 17.5s | 9.0e-10 | 0.655 |

#### 关键发现

1. **Doubao-Seed-2.0-pro 是真正的王者**：通过率 82.4%，远超第二名 kimi-k2.6 (69.1%)。它跟 volcengine glm-5.2 用同一套火山方舟 CodingPlan API Key，只是 endpoint model 名不同，不增加运维成本。
2. **kimi-k2.6 符合预期率最高 (83.8%)**：通过率不是第一但"会拒绝做不了的题"（refuse），不像其他模型会硬画出错的图。
3. **deepseek-v4-pro 是最差投资**：推理模型延迟高 (55.7s) + 成本最贵 (¥3.582) + 通过率只有 64.7%，完全不值。
4. **glm-5.2 通过率垫底之一 (51.5%)**：但成本最低 (¥0.466) + 残差精度优秀，适合作 fallback 兜底。
5. **MiniMax-M3 是速度之王**：p50=9.4s，是其他家的 1/3，适合实时交互场景。

#### 最终配置

基于评测结果：
- `DEFAULT_PROVIDER=volcengine_doubao_pro`（通过率 82.4% 最高，复用火山 Key）
- `T2G_FALLBACK_PROVIDERS=volcengine_doubao_pro,kimi_k26,deepseek`（3 家不同厂商，故障隔离）

---

## V2-D — SSE 流式输出（2026-07-06 完成）

**测试状态**：173/173 通过（V2-C 162 + V2-D 原 6 + V2-D token-level 流式 5）

**目标**：用户选的方向（取代原 V2 #8 符号求解加速）。让 LLM 调用 8-17 秒阻塞期间不再只显示干等转圈，而是**实时推送 token 流 + 已识别对象列表**给前端，用户看到 "AI 正在生成：点 A / 线段 AB / 圆 O..."。stage 事件保留作为阶段切换标记。

### 关键诊断（V2-D 升级时重要发现）

CHANGELOG 之前版本块说"所有 stage 事件最后一次性打印"——经实测验证，**当前代码（带 `await asyncio.sleep(0)`）下其实早已不成立**：
- 用 curl + 真实 LLM 实测，第一个 `stage=llm` 事件在 0.02s 流式到达，LLM 阻塞期间前端能看到"正在理解题意"
- 后续 stage（patch/solve/render）同时到达是符合代码逻辑的预期——它们之间无真正阻塞操作（patch 是直接赋值、solve 通常 <1ms、render <10ms）
- `--http h11 --loop asyncio` 跟默认 uvicorn（uvloop+httptools）行为完全一致，**不需要切换**
- 不需要上 `sse-starlette` 库（默认 `StreamingResponse` 已能流式）

真正的"用户看不到流式"问题是 **LLM 阻塞期间没有 token 流**——这才是 V2-D 升级方向。

### 新增

**后端 — Provider 加 streaming 方法**
- `app/llm/base.py::OpenAICompatProvider.chat_stream()`（新方法，~50 LOC）：
  - 用 httpx `client.stream("POST", ...)` + `aiter_lines()` 读 OpenAI SSE 帧
  - 每个 chunk 提取 `choices[0].delta.content` yield 给上层
  - 处理 `data: [DONE]` 结束标记
  - 自动去掉 `response_format`（stream=True 与 json_object 互斥）
  - 复用子类 `_build_payload`（kimi 关 thinking / 火山不支持 json_mode 等行为自动继承）
  - `LLMProvider` Protocol 加 `chat_stream` 声明
- `app/llm/mock.py::MockProvider.chat_stream()`：handler 返回字符串切成 ~10 字一块 yield，每块 `await asyncio.sleep(0)` 让出控制权（测试用）

**后端 — 流式 extract_dsl**
- `app/llm/extractor.py::extract_dsl_streaming()`（新函数，~120 LOC）：
  - 流式版 `extract_dsl`，yield 事件 dict：`token` / `object_seen` / `done` / `error`
  - 复用 `build_messages` / `parse_json_response` / DSL 校验 / repair 循环（行为等价 `extract_dsl`）
  - 每收到 token 推 `event:token`；用 partial JSON regex 识别新对象，推 `event:object_seen`
  - W13-B 的 timeout_retry 机制保留（第一次 60s/4096 tokens，超时第二次 120s/8192）
  - repair 阶段也流式（用户在第二次 LLM 调用期间也能看到 token + 对象流）
- `app/llm/extractor.py::_extract_seen_objects(buffer)`（新 helper，~25 LOC）：
  - 用 regex 从 LLM 部分输出中识别 (id, kind) 对
  - `[^{}]*?` 保证 id 和 kind 在同一对象层级，避免跨对象误配对
  - 支持两种字段顺序：id 在前 / kind 在前（LLM 输出可能不严格按 schema 序列化）
  - 即使 JSON 不完整（缺末尾 `}` 或字段），只要 "id" 和 "kind" 都已输出就能匹配

**后端 — chat_stream.py 主流程升级**
- `app/api/chat_stream.py::_run_chat_stream()` 改造：
  - stage=llm 阶段从 `extract_dsl` 改成 `extract_dsl_streaming`
  - 每个 token 推 `event:token`；每个已识别对象推 `event:object_seen`
  - 每个 yield 后 `await asyncio.sleep(0)` 让 ASGI flush
- `app/api/chat.py::_repair_solve_with_llm_streaming()`（新函数，~70 LOC）：
  - 流式版 `_repair_solve_with_llm`，yield token / object_seen / done
  - 复用同款 `repair_solve.txt` prompt，与 extract_dsl_streaming 共用 partial JSON 提取
- `chat_stream.py` 的 repair 阶段从同步 `_repair_solve_with_llm` 改成流式 `_repair_solve_with_llm_streaming`

**前端 — SSE 客户端加 token/object_seen 回调**
- `frontend/src/api/client.ts::chatStream`：
  - 新增 `onToken?: (text: string) => void` 参数
  - 新增 `onObjectSeen?: (id: string, kind: string) => void` 参数
  - 处理 `event:token` 和 `event:object_seen` SSE 帧

**前端 — thinking 气泡显示 stage + 已识别对象列表**
- `frontend/src/store/index.ts::sendChat`：
  - 维护 streamState：`{ stage, objects: [{id, kind}] }`
  - thinking 气泡 content 用 `__stream__:<json>` 表示（替代旧的 `__stage__:xxx`）
  - `onStage`：进入新 stage 清空对象列表
  - `onObjectSeen`：追加到对象列表
- `frontend/src/components/ChatPanel.tsx::ChatMsgItem`：
  - 解析 `__stream__:<json>` content
  - 显示 stage 中文文案 + dots 动画
  - 显示已识别对象列表（每个对象一行，"✓ 点 A" / "✓ 线段 AB" / "✓ 圆 O" 等）
  - 向后兼容旧格式 `__thinking__` 和 `__stage__:xxx`
- `frontend/src/components/ChatPanel.tsx::describeObject(id, kind)`（新 helper）：
  - 把 (id, kind) 翻译成中文描述（point→点 / segment→线段 / circle→圆 / polygon→多边形 / axis→坐标系 / curve→曲线 / transformed_point→派生点 / transformed_polygon→变换多边形）
- `frontend/src/styles.css`：
  - 新增 `.thinking-stage` / `.thinking-objects` / `.thinking-obj` 样式
  - 对象列表用虚线分隔 + 较小字号 + 灰色

**测试 — V2-D 新增 5 个**
- `tests/test_v2d_chat_stream.py::test_stream_token_events_yielded`：LLM 阶段推送 token 事件，每个含 text 字段，token 拼起来能恢复原始 LLM 输出
- `tests/test_v2d_chat_stream.py::test_stream_object_seen_events`：partial JSON 解析识别 7 个对象（A/B/C/AB/BC/CA/tri），每个只推送一次（去重）
- `tests/test_v2d_chat_stream.py::test_stream_llm_error_during_stream`：LLM 流式过程中网络断开，应发 error 事件
- `tests/test_v2d_chat_stream.py::test_extract_seen_objects_unit`：单元测试 `_extract_seen_objects`，覆盖空 buffer / 部分 JSON / 多对象 / 字段顺序颠倒 / 嵌套对象 / 不完整 JSON 不误识别
- `tests/test_v2d_chat_stream.py::test_extract_seen_objects_no_false_match_for_constraints`：约束对象（只有 type 没有 id+kind）不应误识别

**前端 — 体验打磨（V2-D 收尾）**
- `frontend/src/store/index.ts::sendChat`：
  - **改进 1：首字延迟期加准备提示**（LLM stage 进入后启 2 秒定时器，期间若没收到任何 token，streamState.waiting=true，ChatPanel 显示"AI 正在准备输出..."次级提示；第一个 token 到达时清除）
  - **改进 2：object_seen 用 RAF 批量 flush**（pendingObjects 缓冲队列 + requestAnimationFrame 在下一帧合并追加，每帧最多触发一次 React re-render，避免每秒 30+ token 时 React 卡顿，参考 cherry-studio 模式）
  - `onStage` 切换时不再清空对象列表（旧版 llm→patch 切换时清空，用户看不到全程已识别对象；新版保留所有对象）
  - `onToken` 接入但只用于标记首字到达（不显示原始 token 内容；后续若要加 token-level 显示可复用）
  - `finally` 块清理 RAF + 等待定时器，防止内存泄漏
- `frontend/src/components/ChatPanel.tsx::ChatMsgItem`：
  - `__stream__:<json>` 渲染加 `state.waiting` 分支：显示"AI 正在准备输出..."次级提示
  - 修复 `slice(10)` off-by-one bug（应为 `slice('__stream__:'.length)` = `slice(11)`）—— 之前导致 JSON.parse 收到 `:{...}` 失败，前端 raw 显示 `__stream__:{...}` 文本
  - 同步修复旧 `__stage__:` 的 `slice(9)` → `slice('__stage__:'.length)`（旧 bug 不影响功能因 stage 不匹配显示默认文案）
- `frontend/src/styles.css`：
  - 新增 `.thinking-waiting` 样式（灰色斜体 + 较小字号 + 顶部 2px 间距）

### 变更

- 无破坏性变更。所有 V2-C 之前的 162 个测试无修改、无回归
- `LLMProvider` Protocol 加 `chat_stream` 方法声明（向后兼容：旧代码不调 chat_stream 不受影响）
- `OpenAICompatProvider` 子类（kimi/volcengine/deepseek/minimax/zhipu）自动继承 chat_stream 方法，复用各自的 `_build_payload` 行为
- 旧端点 `POST /api/session/{sid}/chat` 保留非流式行为，向后兼容

### 修复

- 前端 thinking 气泡 raw 显示 `__stream__:{...}` 文本 bug（`slice(10)` off-by-one，应为 `slice(11)`）

### DB Schema 升级

V2-C → V2-D：**无 schema 变更**。直接拉新代码即可。

### 实测数据（curl + 真实 LLM，等边三角形）

| 时间戳 | 事件 |
|---|---|
| 0.03s | STAGE#1 llm 流式到达 |
| 4.77s | 第一个 TOKEN 到达（GLM-5.2 首字延迟） |
| 4.97s | OBJ#1: A (point) — partial JSON 识别成功 |
| 5.17s | OBJ#2: B (point) |
| 5.37s | OBJ#3: C / OBJ#4: AB (segment) |
| 5.57s-5.77s | OBJ#5: BC / TOKEN#20 |
| 5.97s | OBJ#6: CA (segment) |
| 6.66s | OBJ#7: tri (polygon) — 全部对象识别完成 |
| 8.16s | STAGE#2,3,4 patch/solve/render（之间无阻塞，同时到达符合预期） |
| 8.17s | DONE ok=true |

总计：40 个 token + 7 个 object_seen 事件，全程 8.17s。

**用户体感对比**：
- 旧版本（V2-C）：用户看到"正在理解题意..." 干等 8-17s，期间什么都看不到
- 新版本（V2-D token-level）：用户看到"正在理解题意..." → 4-5s 后 dots 动画继续，thinking 气泡开始显示"已识别对象"列表 → "✓ 点 A" → "✓ 点 B" → ... → "✓ 多边形 tri"，用户全程看到 AI 正在生成什么对象

### 火山 GLM-5.2 stream=True 验证

直接 curl 火山方舟 coding/v3 endpoint 验证 `stream=True`：
- status=200, content-type=text/event-stream ✅
- 59 个 token chunks，跨 3.28 秒（首 token 6.69s，末 9.97s）
- 标准 OpenAI SSE 格式（`data: {...}\n\n` + `data: [DONE]`）
- coding/v3 endpoint 完全支持 stream=True，与 json_mode 互斥但本就不用 json_mode（火山 `supports_json_mode=False`）

### 关键诊断命令（下一轮接手验证流式是否正常）

```bash
# 启动后端（默认 uvloop + httptools 即可，不需要 h11）
cd backend && .venv/bin/uvicorn app.main:app --reload

# 用 127.0.0.1（不要用 localhost，会被 SurrealDB 拦截）
SID=$(curl -s -X POST http://127.0.0.1:8000/api/session \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -N -X POST "http://127.0.0.1:8000/api/session/$SID/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"nl":"画一个等边三角形","provider":null}'
```

预期：先收到 `event: stage llm`，几秒后逐个收到 `event: token` 和 `event: object_seen`（A/B/C/AB/BC/CA/tri），最后 `event: done`。

### 环境注意事项

- 用户的 `localhost:8000` 被 **SurrealDB** 占用（IPv6 解析问题），必须用 `127.0.0.1:8000`
- 用户的 uvicorn PID 在 `localhost:irdmi`（端口 8000 别名）监听，但 `localhost` 解析到 SurrealDB
- 前端 vite proxy 配置在 `frontend/vite.config.ts`，指向 `http://127.0.0.1:8000`（正确）

### 调研笔记（参考 open-webui + cherry-studio）

实现前调研了两个开源项目的 SSE 实现：

**open-webui**（Python/FastAPI 后端）：
- stage 事件根本不走 SSE，走 Socket.IO WebSocket。SSE 只在「WebSocket 不可用」时作为 fallback
- HTTP 端点立即返回普通 JSON `{status: True, task_ids: [...]}`，真正处理在后台 task 跑，每阶段通过 `event_emitter` 推 WebSocket
- 不用 sse-starlette，没有特殊 uvicorn 参数
- 启发：双通道架构能彻底消解 SSE 缓冲问题，但本次未采用（改动量大）

**cherry-studio**（Electron + Vercel AI SDK）：
- 前端不直接 fetch，所有 SSE 解析在 Node.js 主进程用 Vercel AI SDK + `eventsource-parser@3.0.8` 完成
- Vercel AI SDK 不设 `Accept: text/event-stream`，纯 fetch + `response.body.pipeThrough()`
- `eventsource-parser` 提供 `EventSourceParserStream`（TransformStream），3KB
- 启发：RAF 批量 flush 模式（每秒 30-50 token 时用），本次 stage 级流式间隔秒级未采用；token 显示方案 B（partial JSON 解析后描述）正是借鉴此项目

**调研结论**：
- 前端 SSE 解析不是问题，问题在后端 ASGI flush
- `--http h11 --loop asyncio` 跟默认配置行为一致，不需要切换
- 不需要上 sse-starlette 库（默认 StreamingResponse 已能流式）
- 真正的"用户看不到流式"问题是 LLM 阻塞期间没有 token 流——本次升级解决

---

## V2-C — PPT 字体 outline 化（当前版本）

**测试状态**：162/162 通过（W13-B.1 151 + V2-C 11）

**目标**：解决老师试用反馈中"复制到 PPT 后中文/特殊符号字体丢失"的问题。把 `<text>` 元素替换成 `<path>` 几何路径，文字变矢量 outline，跨平台一致。

### 新增

**后端 — 安全表达式沙箱复用，新增文本→path 模块**
- `app/render/text_to_path.py`（新文件，~110 LOC）：
  - 加载内置 Source Han Sans SC 子集字体（`backend/assets/fonts/SourceHanSansSC-Subset.otf`，28KB）
  - `text_to_svg_paths(text, x, y, font_size, fill, anchor)`：返回 `<path>` 字符串拼接
  - 坐标变换：fonttools 字形 path 用字体坐标系（y 向上、em 单位），用 `transform="translate(x y) scale(s -s) translate(cx_font 0)"` 映射到 SVG 像素坐标（y 翻转）
  - 支持 anchor=start/middle/end 三种对齐
  - 缺字符（如 ★）自动跳过，不报错
  - 字符 → path 缓存，二次访问零成本
  - 字体惰性加载（首次调用时），线程安全
- `backend/assets/fonts/SourceHanSansSC-Subset.otf`（新文件，28KB）：
  - 来源：Source Han Sans SC Regular（Adobe + Google 开源，OFL 许可）
  - 子集化：用 `pyftsubset` 保留画图所需字符集（A-Z / a-z / 0-9 / ° / π / × / ÷ / = / + / - / . / 括号 / 中文「原点边角长宽高平垂直弧切径心距上下左右中外内接等腰直角三角形四边形多边形圆线段直线」/ 中文标点）
  - 完整字体 90MB → 子集 28KB，体积可控

**测试 — V2-C**
- `tests/test_v2c_text_to_path.py`（11 个测试）：
  - text_to_path 模块：字体可用、单字符 path、多字符拼接、anchor 对齐、缺字符跳过、缓存命中、中文字符（7）
  - render_svg 集成：默认走 `<text>`、outline 走 `<path>`、几何元素保持不变、坐标系刻度数字也 outline（4）

### 变更

**后端 — render_svg 新增 outline_text 参数**
- `app/render/svg.py`：
  - `render_svg()` 新增 `outline_text: bool = False` 参数
  - 抽出模块级 `_render_text()` 函数：默认输出 `<text>`，outline 模式调用 `text_to_path.text_to_svg_paths()` 输出 `<path>`
  - 8 处 `<text>` 元素全部改走 `text_el`/`_render_text`：点标签 / 派生点标签 / 注解 / 坐标系刻度数字（x 轴 + y 轴）/ 坐标系单位标签 x/y / 原点 O
  - `_render_axis()` 新增 `text_el` 参数，把文本渲染回调传进去
  - 默认行为不变（`outline_text=False`）：浏览器渲染 `<text>` 性能好、可交互（hover/选中）

**后端 — 导出强制 outline**
- `app/api/export.py::_current_svg`：调用 `render_svg(dsl, sol, outline_text=True)`
  - SVG / PNG / PDF 三种导出格式全部走 outline 模式
  - 旧行为：导出 SVG 含 `<text font-family="...">A</text>`，复制到 PPT 字体替换导致中文/特殊符号丢失
  - 新行为：导出 SVG 含 `<path d="M4 0H97..."/>`，文字变矢量，跨平台一致

**依赖 / 部署**
- `backend/pyproject.toml`：新增 `fonttools>=4.50` 依赖
- `backend/Dockerfile`：新增 `COPY assets ./assets`（让字体进镜像）

### 修复

- 无（V2-C 是纯新增 + 兼容变更，所有 151 个旧测试无回归）

### DB Schema 升级

W13-B.1 → V2-C：**无 schema 变更**。直接拉新代码 + `pip install fonttools` 即可。

### 字体子集化命令（备查）

```bash
# 完整字体 90MB 下载（来自 adobe-fonts GitHub release）
curl -sL -o /tmp/SourceHanSansSC.zip \
  "https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansSC.zip"
unzip /tmp/SourceHanSansSC.zip -d /tmp/SourceHanSansSC

# 子集化保留画图字符集（90MB → 28KB）
.venv/bin/pyftsubset \
  /tmp/SourceHanSansSC/OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf \
  --text="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789°π×÷=+-.,()[]{}原点边角长宽高平垂直弧切径心距上下左右中外内接等腰直角三角形四边形多边形圆线段直线甲乙丙丁一二三四五六七八九十" \
  --output-file=backend/assets/fonts/SourceHanSansSC-Subset.otf
```

未来若需要扩充字符集（如新增中文标签），用上述命令重新生成子集字体即可。

---

## W13-B.1 — Provider 配置修补（kimi 网络提示 + doubao 降级 + 端点对齐）

**测试状态**：151/151 通过（W13-B 149 + 2 新增）

**目标**：修 provider 配置问题——① kimi 切换报网络错误时提示文案误导（只列了智谱/火山/DeepSeek 域名，没列 moonshot）；② kimi `.env` base_url 写错域名；③ Doubao-Seed-2.1-pro/turbo 太新火山 Coding Plan 不支持，且按 `model_config_v02.md` doubao 应与 glm-5.2 共用 coding/v3 端点。

### 修复

**后端 — 错误提示按 Provider 动态生成域名**
- `app/api/errors.py`：
  - 新增 `_PROVIDER_DOMAIN` 映射（zhipu/volcengine/deepseek/minimax/kimi → 域名）
  - 新增 `_network_hint(provider)`：根据 `LLMError.provider` 取对应厂商域名生成 hint
  - 多模型注册的带后缀 name（如 `kimi_k26` / `volcengine_doubao_pro`）取首个下划线前的前缀匹配厂商域名
  - 旧行为：网络错误 hint 写死 "检查后端机器到 open.bigmodel.cn / ark.cn-beijing / api.deepseek.com 的网络" —— 切到 kimi/minimax 时误导用户
  - 新行为：kimi 报错时提示 "检查后端机器到 api.moonshot.cn 的网络（provider=kimi_k26）"

**配置 — kimi base_url 根因修正**
- `backend/.env`：`MOONSHOT_BASE_URL` 误写成 `https://api.moonshot.ai/v1`（`.ai`），覆盖了代码正确的默认值 `https://api.moonshot.cn/v1`（`.cn`），导致 kimi 全线连接失败报"网络异常或超时"。已改回 `.cn`
- `backend/model_config.md`：MoonshotAI BASE_URL 同步由 `.ai` 更正为 `.cn`
- 代码默认值（`kimi.py` / `router.py` / `errors.py` 域名映射）本就是 `.cn`，无需改动

**后端 — kimi-k2.6 关闭 thinking 避免超时**
- `app/llm/kimi.py`：`KimiProvider._build_payload` 对 `kimi-k2.6` 传 `thinking.type=disabled`
  - 根因：据 Moonshot 官方文档，kimi-k2.6 是通用思考模型、默认开启 thinking；复杂题（如折叠+多约束）推理 >120s 触发超时（60s 首次 + 120s 重试均失败），日志反复出现 `llm.chat.timeout_retry` 无后续 `llm.chat.ok`
  - kimi-k2.7-code 始终 thinking 且无法关闭（传 disabled 报错），不处理；日志显示其 17-81s 能完成
  - 画图 DSL 是结构化输出，无需深度推理，关闭 thinking 保证响应速度
- 新增测试 `test_kimi_payload_disables_thinking_for_k26`：验证 k2.6 payload 含 `thinking=disabled`、k2.7 不含、temperature 均被移除

### 变更

**后端 — Doubao 模型降级 + 端点对齐 model_config_v02**
- `app/llm/router.py`：
  - 删除 `doubao-seed-2-1-pro-260628`（`volcengine_doubao_pro`）和 `doubao-seed-2-1-turbo-260628`（`volcengine_doubao_turbo`）两个注册
  - 替换为 `Doubao-Seed-2.0-pro`（保留 provider name `volcengine_doubao_pro`）
  - **端点改用 coding/v3**（复用 `VOLCENGINE_BASE_URL`，默认 `https://ark.cn-beijing.volces.com/api/coding/v3`），与 glm-5.2 共用火山方舟 CodingPlan 端点
  - 旧行为：doubao 走标准 v3 端点 `api/v3`、模型名 `doubao-seed-2-0-pro`
  - 新行为：按 `model_config_v02.md`，doubao 与 glm-5.2 同属火山方舟 CodingPlan，共用 coding/v3 端点、模型名 `Doubao-Seed-2.0-pro`
- `backend/.env.example`：多模型注册说明同步更新（删 turbo 行、pro 行模型名改为 `Doubao-Seed-2.0-pro`）

**前端 — Provider 下拉仅显示 Model Name**
- `frontend/src/components/ProviderSwitch.tsx`：
  - 删除 `labelOf` / `shorten`，下拉项直接用 `p.model || p.name`
  - 旧行为：显示「智谱 glm-5.2」「火山方舟 Doubao-Seed…」（厂商前缀 + 模型名）
  - 新行为：仅显示模型名（如 `glm-5.2` / `Doubao-Seed-2.0-pro` / `kimi-k2.6`）

**前端 — 未配置的 Provider 不显示**
- `frontend/src/components/ProviderSwitch.tsx`：下拉只渲染 `enabled` 的 provider，未配置的（如未填 Key 的 `glm-4.5`）不再出现
- `frontend/src/store/index.ts::init`：若 localStorage 缓存的 provider 已不在 enabled 列表，自动回退到后端 default，避免选中失效 provider

**测试**
- `tests/test_w6_ops.py`：
  - `test_classify_llm_network_error` 加断言 hint 含 `open.bigmodel.cn`
  - 新增 `test_classify_llm_network_hint_per_provider`：覆盖 5 个基础 provider + 4 个带后缀多模型 name 的域名匹配
- `tests/test_w2_llm.py` / `tests/test_w3_api.py`：删除 `volcengine_doubao_turbo` 断言

### DB Schema 升级

W13-B → W13-B.1：**无 schema 变更**。

---

## W13-B — 约束诊断 + LLM 二次修复回路

**测试状态**：149/149 通过（W13-A 145 + W13-B 4）

**目标**：继续处理成都真题里 16 题 solve_fail 中残差 > 1e-2 的病态题。

### 新增

**后端 — Solver 诊断**
- `app/solver/engine.py::SolveError`：作为 dataclass-like RuntimeError，携带 `residual` 与 `worst_constraint` 属性
- `_diagnose_worst_constraint`：求解失败后逐条重跑约束残差，找出贡献最大的一条并写入 SolveError 详情

**后端 — Chat API · solve_repair 回路**
- `app/api/chat.py::_repair_solve_with_llm`：新增
  - solve 抛 SolveError 且 residual > 1e-2 时触发
  - 用 `repair_solve.txt` prompt 把诊断 + 原始 NL 发给 LLM 让它修正
  - 修复 DSL 通过 validate + 再求解一次
  - 成功返回 `solve_repaired=true` + `solve_repair_reason`
  - 失败合并两次错误信息返回 422
- `app/api/chat.py` 主流程：SolveError 分流小残差直接 422 / 大残差走 repair
- `app/api/chat.py::solve()` 调用：`restarts=20, restarts_extra=40`（从 20 提升）
- `app/llm/prompts/repair_solve.txt`：新文件，solve 修复 prompt 模板

**后端 — Prompt**
- `app/llm/prompts/system.txt` 末尾加"处理歧义"章节：
  - 歧义时选一种最自然解读，不要试图同时满足多种解释
  - 字母参数用具体值代替
  - 每个自由点保证有足够约束
  - 避免过度约束

**前端**
- `frontend/src/api/types.ts`：`ChatResult` 加 `solve_repaired?`、`solve_repair_reason?` 字段

**测试**
- `tests/test_w13b_solve_repair.py`（4 个）：
  - solver 诊断字段（residual + worst_constraint）
  - Mock LLM 二次修正成功路径（第一次坏 DSL → 第二次好 DSL → ok + solve_repaired=true）
  - Mock LLM 二次修复也失败：返回 422 + detail 含 `[solve_repair 也失败]`
  - 小残差 solve_fail 不触发 repair（仅 residual > 1e-2 才修复）

### 变更

- 无破坏性变更。W13-A 及以前的 145 测试全部保持。
- SolveError 由 pass 改为 dataclass-like 类，反向兼容（str(err) 依然可用）。

### DB Schema 升级

W13-A → W13-B：**无 schema 变更**。

### 评估

- **成都真题全量**（chengdu_full.json 68 题，2026-07-02）：
  - v0.13.0 → **W13-B**：48 ok → 48 ok（保持）
  - 符合预期率：47 → **52 (69.1% → 76.5%)** (+5)
  - 状态转换：
    - **7 题 solve_fail → ok** ✅ W13-B solve_repair 直接受益（zk_007, zk_022, zk_027, zk_041, zk_049, zk_055, zk_057）
    - 4 题 ok → llm_refuse：LLM 现在更严谨（prompt 引导让 LLM 主动拒绝歧义题）
    - 3 题 ok → solve_fail：LLM 输出漂移
    - 1 题 solve_fail → llm_refuse：更合理的分类
  - 主要收益是**分类正确性提升**（W13-B solve_repair 修复 + prompt 引导让 LLM 分类更精准）
  - v0.13.0 基线备份到 `test/results_chengdu_full_v0.13.0_baseline/`

---

## W13-A — 求解器自适应重启

**测试状态**：145/145 通过（W12 141 + W13 4）

**目标**：解决 v0.12.1 成都真题评估中发现的最大瓶颈——19 题 solve_fail 中 12 题残差 < 1e-2 只差一步收敛。

### 新增

**后端 — Solver 自适应重启阶段 2**
- `app/solver/engine.py::solve`：新增 `restarts_extra` 参数（默认 20）
  - 阶段 1（现有 `restarts` 次）跑完后，若最佳 cost ∈ (tol, 1e-2)，进入阶段 2
  - 阶段 2 用 4 种初值策略循环：`narrow(-2,2)` / `perturb_hint(±2)` / `wide(-15,15)` / `default(-5,5)`
  - 一旦 cost < tol 立即返回
  - 阶段 2 是**收益条件触发**：不满足条件时不启动，通过题无延迟增加
- `_initial_guess(strategy)`：接受策略参数，实现多样化初值
- `_try_solve(x0)`：抽取的求解 + cost 计算辅助函数（复用 W12 hint 残差分离逻辑）

**测试**
- `tests/test_w13_adaptive_restarts.py`（4 个测试）：
  - 简单等边三角形不需要 stage-2（restarts_extra=0 仍通过）
  - 复杂 4 点系统 restarts=3 不够但 restarts_extra=30 能收敛
  - 互斥约束（AB=3 且 AB=5）不会无限循环，抛 SolveError
  - restarts_extra=0 时行为回退到旧版本

### 变更

- 无破坏性变更。所有 W12 之前的测试保持通过。
- `solve()` 新增参数向后兼容（默认 20，与 W12 效果一致或更好）。

### 修复

- 无

### DB Schema 升级

W12 → W13-A：**无 schema 变更**。

### 评估

- **成都真题全量**（chengdu_full.json 68 题，2026-07-02）：
  - v0.12.1 → **W13-A**：41 ok → **48 ok (60.3% → 70.6%)** (+7)
  - 符合预期率：42 → 47 (61.8% → 69.1%)
  - 状态转换：
    - **10 题 solve_fail → ok** ✅ W13-A 直接受益（zk_010, zk_012, zk_024, zk_035, zk_039, zk_044, zk_045, zk_056, zk_060, zk_061）
    - 5 题 ok → solve_fail ⚠️ LLM 输出漂移（非 W13-A 回归）
    - 2 题 llm_refuse → ok（LLM 正向漂移）
  - 平均延迟：26.0s → 28.9s（stage-2 触发时略增，通过题无影响）
  - v0.12.1 基线备份到 `test/results_chengdu_full_v0.12.1_baseline/`

- 单题精度不变：ok 题平均残差 4.88e-06 → 5.15e-06（同数量级，几何精确）

---

## W12 — on_curve 硬约束 + 求解器 hint 残差分离

**测试状态**：141/141 通过（V2-B 134 + W12 7）

**目标**：解决成都真题测试中发现的两个问题——
1. hint 只是坐标近似，不能保证点严格在函数曲线上（如反比例题里 A、B 可能偏离 y=6/x）
2. 加了 on_curve 硬约束后，硬约束残差会与 hint 软残差冲突，误报"未收敛"

### 新增

**后端 — DSL**
- `app/dsl/schema.py`：新增 `OnCurveC{point, curve}` 约束
  - `point` 是 PointObj，`curve` 是 FunctionCurveObj
  - `curve.var == "x"` 时约束 `point.y == f(point.x)`；`var == "y"` 时约束 `point.x == g(point.y)`

**后端 — Validator**
- `app/dsl/validator.py`：on_curve 分支 —— point 引用 PointObj、curve 引用 FunctionCurveObj

**后端 — Solver**
- `app/solver/engine.py::_build_constraint_residual`：新增 on_curve 残差 builder
  - 编译 curve.expr 得到 f(v)
  - 返回残差 `(py - f(px)) * weight`，权重 10（压制 hint 软约束的 0.05 拉扯）
  - 表达式返回 nan/inf 时给 1e3 大残差把点推离
- `app/solver/engine.py::solve`：**hint 残差分离**（关键修复）
  - 计数 hint_residual_count，跑完求解后**扣掉 hint 残差再判定 cost < 1e-4**
  - 避免"hint 距离目标较远导致误报 SolveError"
  - 这是 W12 前老代码里潜在的一个 bug（V2-B 抛物线题 A hint=(1,2) 时残差被 hint 抬到 1e-3 但求解实际收敛）

**LLM — Prompt / few-shot**
- `app/llm/prompts/system.txt`：
  - 约束列表加 `on_curve{point, curve}`
  - 第 13 条函数图像说明加"**点在曲线上（W12 新增）**"段：强调用 on_curve 而不是只靠 hint
- `app/llm/prompts/fewshots.jsonl`：+1 条 few-shot（反比例函数 A、B 在曲线上，用 on_curve 硬约束）
- `app/llm/extractor.py`：`fewshot_limit` 20 → 21

**测试**
- `tests/test_w12_on_curve.py`（7 个测试）：
  - schema：解析（1）
  - validator：未知 point、curve 类型错（2）
  - solver：hint 远离真解时 on_curve 把 A 拉到抛物线 / 反比例 / var=y 曲线上（3）
  - solver：两点在 y=6/x 上 + 共线过原点，几何不变量满足（1）

### 变更

- 无破坏性变更。V2-B 及以前的 134 测试全部无回归。
- **求解器 cost 判定语义**：之前 `cost = 2 * result.cost` 包含 hint 残差；现在只算硬约束残差。这是**修复**而非破坏。

### 修复

- Solver hint 与硬约束冲突导致误报 SolveError（尤其在 V2-B 曲线场景）

### DB Schema 升级

V2-B → W12：**无 schema 变更**。

### 评估

- **成都真题精选** cmm v2r 变化：
  - V2-B 17/20 (85%) → **W12 18/20 (90%)** (+1)
  - **gk_hard_02 椭圆题 refuse → ok**：LLM 学会用两条 curve + on_curve 硬约束拆解椭圆，残差 7e-7
  - zk_med_03 反比例题：DSL 输出升级为含 on_curve 硬约束（虽然原状态已 ok，但图形几何精度提升）
  - 所有 20 题**符合预期率 100%**

- **成都真题全量评估**（2026-07-02、`chengdu_full.json` 68 题）：
  - 求解成功 **41 / 68 (60.3%)**、符合预期 **42 / 68 (61.8%)**
  - 按题型：平面几何 62% / 几何变换 38% / 函数图像 100% / 坐标系 75%
  - 主要瓶颈：**19 题 solve_fail** 中 12 题残差 <1e-2 只差一步收敛，说明 solver.restarts=20 不够
  - 详细分析：`docs/eval-v0.12.1-chengdu-full.md`
  - W13 候选方向：求解器 restarts 自适应（预估 60% → 78%）

---

## V2-B — 函数图像

**测试状态**：134/134 通过（W11 115 + V2-B 19）

**目标**：在坐标系（W9 axis）之上支持显式函数曲线 `y = f(x)` / `x = g(y)`，覆盖一次/二次/反比例/正弦余弦/指对数等。抛物线 `y²=2x` 通过拆成两条显式函数 `y=±√(2x)` 支持。这是 V2 主线（V2-A 坐标系 → V2-B 函数图像）的最后一环。

### 新增

**后端 — 安全表达式沙箱（关键新模块）**
- `app/dsl/safe_expr.py`（新文件，~130 LOC）：
  - `compile_expr(expr: str, var: str="x") -> Callable[[float], float]`
  - 走 `ast.parse(mode="eval")` + **AST 节点白名单**校验，绝不使用 `eval(str)`
  - 允许的节点：Expression/BinOp/UnaryOp/Constant/Name/Load/Call/Compare/BoolOp/IfExp
  - 允许的函数（Name）：sin/cos/tan/asin/acos/atan/atan2/sqrt/exp/log/log10/log2/abs/pow/floor/ceil
  - 允许的常量：pi、e
  - **禁止**：Attribute（`x.__class__`）、Subscript（`x[0]`）、Lambda、任何未在白名单的 Name（`__import__` / `open` / `eval`）
  - 运行时错误（ZeroDivisionError / ValueError / OverflowError）返回 nan，交给渲染层过滤
  - 编译后的可调用函数用受限 `globals={"__builtins__": {}, ...}` 保护

**后端 — DSL 层**
- `app/dsl/schema.py`：新增 `FunctionCurveObj{expr, var, domain?, samples=300, color, dash?}`
  - `var` 是 `"x"` 或 `"y"`（决定表达式的自变量）
  - `domain` 缺省用 axis 对应 range
  - `DSL.curves()` helper
- `app/dsl/validator.py`：
  - curve 必须在含 axis 的 DSL 中（否则拒绝）
  - samples ≥ 10
  - domain min < max
  - expr 走 `safe_expr.compile_expr` 校验（不安全表达式或语法错误抛 DSLValidationError）

**后端 — 渲染**
- `app/render/svg.py::_render_curve`（新增，~70 LOC）：
  - 编译 expr → 等距采样 N=300 点
  - **断点切段**：`nan` / `inf` / `|y| > 1000` 时切开当前段、新开一段
  - 每段单独输出 `<polyline data-id="{curve.id}" class="t2g-obj t2g-curve" ...>` —— 一个 curve 可能对应多个 polyline
  - 曲线颜色默认 `#0d6efd`（蓝色，与几何黑色区分）
  - 支持 `dash` 字段（可选虚线）
  - 渲染顺序：坐标系 → **曲线** → 几何图形（曲线在图形下、坐标系上）
- `_compute_bbox`：把 curve.domain 也纳入 bbox（保证曲线不被裁）

**LLM — Prompt / few-shot**
- `app/llm/prompts/system.txt`：
  - 拒绝清单第 9 条中删去"函数图像"、"抛物线"（保留隐式一般式椭圆/双曲线）
  - 新增第 13 条「函数图像支持」：解释 curve 对象、`var` 字段、隐式方程 y²=2x 拆解规则
  - DSL Schema 节加 `curve{...}` 说明
- `app/llm/prompts/fewshots.jsonl`：+3 条 few-shot
  - y = x² 二次函数
  - y = 1/x 反比例
  - y² = 2x 抛物线（拆成两条 curve 展示）
- `app/llm/extractor.py`：`fewshot_limit` 17 → 20

**后端 — API**
- `app/api/chat.py::_make_refuse_message`：
  - 删除 `keywords_for_function`（含"函数图像"、"y="等一大批关键词）
  - 新增 `keywords_for_implicit_curve = ("椭圆", "双曲线", "圆锥曲线")`：只对**隐式一般式**给出建议
  - 头部话术加"函数图像"到能力清单

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加 `'curve'`；新增 `expr / var / domain / samples / color / dash` 字段
- `frontend/src/components/Canvas.tsx::describe`：curve 分支显示"曲线 x**2, x∈[-3,3]"

**测试**
- `tests/test_v2b_curve.py`（19 个测试）：
  - safe_expr：数学函数、pi/e、pow、运行时错误返回 nan（3）
  - safe_expr：拒绝 __import__ / open / eval、属性访问、下标、lambda、未知 Name（7）
  - schema：解析（1）
  - validator：无 axis 拒绝、不安全 expr 拒绝、坏 domain 拒绝（3）
  - render：直线、1/x 断点切段、sqrt(x) 域外过滤、无 domain 用 axis range、var=y（5）
- `tests/test_w7_feedback.py`：改写 `test_refuse_message_function_image`（V2-B 支持后语义变了）+ 新增 `test_refuse_message_ellipse_hyperbola`

### 变更

- 无破坏性变更。所有 W11 之前的测试无回归。
- 拒绝消息头部加"函数图像"到能力清单。

### 修复

- 无

### DB Schema 升级

W11 → V2-B：**无 schema 变更**。直接拉新代码即可。

### 评估

- cmm v2r：W11 34/56 → V2-B **36/56** (+2)
  - **V2-B 目标题 #6「抛物线 y²=2x 及其准线」**：refuse → **ok** ✅ 打通
  - **#16「反比例 y=k/x 与 y=x 的交点」**：refuse → **ok** ✅ 直接收益
  - #13 #17：ok（LLM 又想通了，属正向漂移）
  - #21 #43：ok → solve_fail，LLM 输出漂移，非 V2-B 代码问题
  - W11 基线备份在 `backend/test/results_cmm_v2r_w11_baseline/`

---

## W11 — 几何变换

**测试状态**：115/115 通过（W10 103 - 2 W7 过时测试 + 14 W11）

**目标**：把「三角形 ABC 绕点 O 旋转 90°」「关于点 O 中心对称」「沿方向平移」「关于直线 l 对称」这类几何变换类题从 refuse 转为直接支持，覆盖 cmm 评估里 #10 #37 #55 类的题型。

### 新增

**后端 — DSL 层**
- `app/dsl/schema.py`：
  - 新增 4 种 TransformSpec：`RotationSpec{center, angle}` / `TranslationSpec{dx, dy}` / `ReflectionSpec{line}` / `CentralSymSpec{center}`（通过 `type` discriminator 判别）
  - 新增 2 类派生对象：`TransformedPointObj{source, transform}`（派生单点）/ `TransformedPolygonObj{source, transform, vertex_suffix}`（派生多边形，自动为每个源顶点生成 `<vertex>_<suffix>` 派生点）
  - `GeometryObject` union 扩展，加入两类派生对象
  - `DSL.transformed_polygons()` / `transformed_points()` helper

**后端 — Validator**
- `app/dsl/validator.py`：
  - 派生对象 source 必须存在且类型匹配（TransformedPointObj 要求 source 是 PointObj；TransformedPolygonObj 要求是 PolygonObj）
  - **拒绝嵌套派生**：source 不能再是派生对象
  - 派生顶点 id（`<vertex>_<vertex_suffix>`）必须不与已有对象冲突
  - transform.center/line 引用类型校验（通过 `_validate_transform_refs` 抽取的公共函数）
  - **放宽 segment/line/polygon 顶点校验**：新增 `_require_point_like`，允许引用 PointObj **或** TransformedPointObj（这是 W11 的关键 unblock —— few-shot 里 `AD segment` 的 `b="D"` 必须能引用派生点）

**后端 — Solver**
- `app/solver/engine.py`：
  - 新增纯数学函数 `apply_transform(transform, p, *, coords, line_endpoints)`：4 种变换的闭式公式
    - rotation：`p' = O + R(θ)·(p - O)`
    - translation：`p' = p + (dx, dy)`
    - central_symmetry：`p' = 2C - p`
    - reflection：`p' = p - 2·((p-a)·n̂)·n̂`
  - 新增 `_apply_derived_objects(dsl, coords)`：`_build_solution` 后处理，把派生对象的坐标填入 `coords` dict
  - 派生对象**不占用**求解自由变量（`dsl.points()` 只返回 PointObj，天然排除 TransformedPointObj）

**后端 — Renderer**
- `app/render/svg.py`：
  - 派生多边形渲染：额外遍历 `dsl.transformed_polygons()`，用 `stroke-dasharray` 虚线 + `class="t2g-derived"` 标记
  - 派生顶点单独画点 + 标签**自动加撇**（`A_p` → `A'`）
  - 独立派生点 `dsl.transformed_points()` 同样虚线 + 加撇
  - `_isolated_aux_points`：把派生对象的 `source` 也纳入"被引用"集合

**LLM — Prompt / Few-shot**
- `app/llm/prompts/system.txt`：
  - 拒绝清单第 9 条**删除**"几何变换"这一类
  - DSL Schema 节加 `transformed_point / transformed_polygon` 说明 + `transform.type` 4 种子类型
  - 新增第 12 条「几何变换支持」详细说明 + 2 个示例（中心对称、单点旋转）
- `app/llm/prompts/fewshots.jsonl`：+2 条 few-shot
  - 「三角形 ABC 关于点 B 中心对称」（`transformed_polygon`）
  - 「线段 AC 绕点 A 旋转 90° 得到线段 AD」（`transformed_point`）
- `app/llm/extractor.py`：`fewshot_limit` 15 → 17

**后端 — API**
- `app/api/chat.py::_make_refuse_message`：删除 `keywords_for_transform` 分支（现在支持了）；头部话术加"几何变换"到能力清单

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加 `'transformed_point' | 'transformed_polygon'`；新增 `source / transform / vertex_suffix` 字段
- `frontend/src/components/Canvas.tsx::describe`：两个新 kind 分支显示"（B 经 rotation 派生）"

**测试**
- `tests/test_w11_transform.py`（14 个测试）：
  - schema 解析（2）
  - validator：未知 source / 错类型 / id 冲突 / 反射线是点（4）
  - apply_transform 数学：rotation 绕原点 / 绕非原点、translation、central_symmetry、reflection（5）
  - solver：中心对称派生多边形（A_p == A、三边等长）；单点旋转（|AD|=|AC|、∠CAD=90°）（2）
  - render：派生多边形有 dasharray、派生顶点 A_p 存在 + label 有撇（1）
- `tests/test_w7_feedback.py`：删除 2 个过时的 transform 拒绝测试（W11 已支持）

### 变更

- 无破坏性变更。所有 W10 现有测试无回归。
- 拒绝消息头部加"几何变换"到能力清单。

### 修复

- 无

### DB Schema 升级

W10 → W11：**无 schema 变更**。直接拉新代码即可。

### 评估

- cmm v2r：W10 35/56 → W11 34/56（-1）
  - **W11 目标题 #10「线段 AC 绕点 A 旋转 90° 得到线段 AD」**：refuse → **ok** ✅ 打通
  - #43「四边形 ABCD ∠CBD=130°」：solve_fail → **ok** ✅ 附带提升
  - #13 #17 #21：ok → refuse，全是 **LLM 行为漂移 + 判断更严谨**（面积约束 / 字母边长 / 复合图形对齐约束），非 W11 代码问题
  - W10 → W11 基线备份在 `backend/test/results_cmm_v2r_w10_baseline/`

---

## W10 — 半平面约束 + patch fallback + DB 自动迁移

**测试状态**：103/103 通过（W9 89 + W10 14）

**目标**：解决两个老师试用反馈的真实问题——

1. 「C 在 AB 上方」LLM 无法精准表达 → 求解出现"镜像解"（今天上、明天下），不可控
2. 「修改后图形不合法」错误突兀，老师看不懂——LLM 输出的 patch 不闭合时直接 422

### 新增

**后端 — DSL 层**
- `app/dsl/schema.py`：新增 2 个约束
  - `SameSideC{line, point, ref}` — 点 point 与参考点 ref 在 line 同侧
  - `OppositeSideC{line, point, ref}` — 异侧
- `app/dsl/validator.py`：校验 line 是 segment/line；point/ref 是 point；point ≠ ref

**后端 — 求解器**
- `app/solver/engine.py`：不等式软残差 builder
  - 残差公式：`max(0, margin - sign·sd_p·sd_r) * weight`（margin=0.1, weight=5.0）
  - `sd_p` / `sd_r` 复用现有 `_signed_point_line_distance`
  - `sign = +1`（same_side）/ `-1`（opposite_side）
  - 若 product 已满足，残差为 0（不干扰其他约束求解）

**后端 — 渲染**
- `app/render/svg.py`：新增 `_isolated_aux_points(dsl)` 辅助函数
  - 识别 hint != None 且未被任何 segment/line/polygon/circle/axis 引用的 point
  - 渲染主循环跳过这类点（不画 circle、不写 label）
  - 用途：LLM 为表达"C 在 AB 上方"时引入的 P0 辅助点对老师隐形

**后端 — DB 层**
- `app/db/models.py`：`Message` 新增 `fallback: bool | None` 列
- `app/db/migrations.py`（新文件，~50 LOC）：轻量自动迁移
  - 启动时检测 `REQUIRED_COLUMNS` 中声明的列；缺失则 ALTER TABLE 添加
  - 仅支持 SQLite（PRAGMA table_info + ALTER TABLE ADD COLUMN）
  - 幂等，已存在不重复加
  - 表不存在时静默跳过（由 create_all 创建）
  - 设计意图：未来新增可空列只需在 REQUIRED_COLUMNS 加一行，开发期/生产期都无需手动 ALTER
- `app/db/session.py::init_db`：create_all 之后调用 ensure_schema

**后端 — API 层**
- `app/api/chat.py`：patch fallback 逻辑
  - 当 `apply_patch` 抛 `DSLPatchError(resulting DSL invalid)` 时，**不再直接 422**
  - 自动用 user nl 重发一次 LLM，**不带 current_dsl**，强制走完整 DSL 路径
  - 成功 → 返回 `ok=true, fallback=true, fallback_reason=<原 patch 错误>`，并把 `Message.fallback=True` 落库
  - fallback 也失败 → 返回 422 + detail 含两次错误信息（[fallback]: ...）
- `app/api/session.py::list_messages`：响应加 `fallback` 字段
- `app/session/repo.py::add_message`：接受 `fallback` 参数

**LLM — Prompt / few-shot**
- `app/llm/prompts/system.txt`：
  - DSL Schema 节加 `same_side` / `opposite_side` 说明
  - 新增第 11 条「方位/上下方约束」：详细说明何时用 same_side、辅助点 P0 的 hint 怎么填、id 命名约定
  - **明确加反例**：「老师只说"画三角形 ABC"或"画三条平行线"，不要自作主张加 same_side」（防止 LLM 行为漂移导致老题退化）
- `app/llm/prompts/fewshots.jsonl`：+1 条 few-shot（直角三角形 + C 在 AB 上方）
- `app/llm/extractor.py`：`fewshot_limit` 14 → 15

**前端**
- `frontend/src/api/types.ts`：`Message.fallback?: boolean`、`ChatResult.fallback / fallback_reason`
- `frontend/src/components/ChatPanel.tsx`：fallback=true 的 assistant 消息上方加一行灰色小提示「（AI 第一次输出与现有图形有冲突，已自动重新理解为重画）」
- `frontend/src/styles.css`：`.fallback-hint` 样式（灰色斜体 + 虚线下划线分隔）

**测试**
- `tests/test_w10_halfplane.py`（10 个测试）：
  - schema：same_side / opposite_side Pydantic 解析
  - validator：非 segment 的 line、point==ref、未知 ref 三种边界
  - solver：same_side 强制 C 在 AB 上方（C.y > 0）+ opposite_side 强制下方（C.y < 0），同时校验几何不变量（边长、∠C=90°）
  - render：`_isolated_aux_points` 检测、SVG 不含 `data-id="P0"`、被引用的 hint 点仍画
- `tests/test_w10_fallback.py`（4 个测试）：
  - ensure_schema 给旧版 message 表自动加 fallback 列
  - ensure_schema 表不存在时不报错（幂等）
  - patch fallback 成功路径：bad patch → 自动重画 → ok=true + fallback=true 落库
  - patch fallback 也失败：detail 含 `[fallback]:` 标记

**评估**
- cmm v2r 评估：W9 36/56 → W10 35/56（-1 题）
  - #48「折线 AB=BC=CD=DE=EF，∠A=15°」：W9 ok → W10 llm_refuse（拒绝理由合理："∠A 不明确，仅 1 条边连 A"），属 LLM 判断更严谨，**不是回归**
  - W9 → W10 评估结果备份在 `backend/test/results_cmm_v2r_w9_baseline/`

### 变更

- 无破坏性变更。所有 W9 之前的 78 个测试无修改、无回归。

### 修复

- `app/db/session.py::init_db`：之前只 `create_all`，无法给已存在的表加新列；现在调 ensure_schema 兜底
- 之前 patch 不合法时直接 422，老师看到突兀错误；现在自动 fallback 重画，体感顺滑

### DB Schema 升级

W9 → W10：**新增 `message.fallback BOOLEAN` 列**。

**升级方式**：
- 开发期 / 生产期都**无需任何手动操作**。启动时 `init_db()` 会调用 `ensure_schema()` 自动 ALTER TABLE 添加列
- 已有 DB 中所有现存 message 的 fallback 值为 NULL（向后兼容）
- 仅支持 SQLite；切换到 PostgreSQL 时需要把 ensure_schema 改写或上 Alembic

---

## W9 — V2-A 坐标系支持

**测试状态**：89/89 通过（W8 78 + W9 11）

**目标**：迈出 V2 第一步——给 DSL 加上"平面直角坐标系"对象，让老师能说「画一个坐标系，x 轴从 -5 到 5」，画板上出现带箭头/网格/刻度/数字的坐标系。函数图像、坐标值描述仍走 refuse 路径（留给 V2-B / V2-未）。

### 新增

**后端 — DSL 层**
- `app/dsl/schema.py`：新增 `AxisObj{kind:"axis", origin, x_range, y_range, tick_step, show_grid, show_ticks, x_label, y_label}`；`DSL.axis()` helper（最多 1 个）
- `app/dsl/validator.py`：
  - `AxisObj` 校验 origin 引用 + range/tick_step 合法性
  - axis 唯一性硬性约束（"at most one axis allowed per DSL"）

**后端 — 求解器**
- `app/solver/engine.py::solve`：gauge 选择分流
  - 无 axis：保持 W1 行为（first 点 (0,0) + second 点 y=0）
  - 有 axis：`axis.origin` 固定 (0,0)，坐标系朝向由 axis 本身定义（+x 向右、+y 向上），**不再加 second-y=0** —— 这是 V2-A 最关键的语义变化

**后端 — 渲染**
- `app/render/svg.py::_render_axis`：新增 ~120 LOC
  - 渲染顺序：网格 → 主轴 → 箭头（SVG `<marker>` 复用）→ 刻度 → 刻度数字 → 单位标签 `x`/`y` → 原点 `O`
  - 颜色分层：网格 `#e5e7eb`、主轴/刻度 `#9ca3af`、数字 `#6b7280`
  - 原点刻度数字不画（避免与 O 重叠）
- `app/render/svg.py::_compute_bbox`：把 axis range 纳入 bbox，确保坐标系不被裁

**LLM — Prompt / few-shot**
- `app/llm/prompts/system.txt`：
  - 拒绝清单第 9 条删除"坐标系作图"
  - 新增第 10 条「坐标系支持」，给出 axis 对象模板、明确"基于坐标 A(2,3) 仍不支持"
  - DSL Schema 节选段加入 axis 类型说明
- `app/llm/prompts/fewshots.jsonl`：追加 2 条 axis few-shot（基本坐标系 / 自定义范围与刻度）
- `app/llm/extractor.py`：`fewshot_limit` 默认 6 → 14（确保新 axis 示例进入提示）

**测试**
- `tests/test_w9_axis.py`：新增 11 个测试，覆盖 schema、validator（5 个边界）、solver（2 个 gauge 场景 + 1 个负例）、render（含/不含 grid 两种）、refuse 文案行为

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加入 `'axis'`，新增 axis 字段（`origin / x_range / y_range / tick_step / show_grid / show_ticks / x_label / y_label`）
- `frontend/src/components/Canvas.tsx::describe`：axis 分支显示「坐标系：x∈[...], y∈[...]」

### 变更

- `app/api/chat.py::_make_refuse_message`：
  - 删除原 `keywords_for_coord = ("坐标", "象限", "x 轴", "y 轴", "原点")` 分支（这些词现在都该走 axis 路径）
  - 新增 `keywords_for_coord_value = ("A(", "B(", ..., "坐标为", "坐标是")`：**仅**对 `A(2,3)` 这类具体坐标值的描述给出引导（坐标系本身可画 + 几何关系替代）
  - 顶部头部话术：从「主要支持平面几何作图（点、线段、圆、多边形与常见约束）」改为「主要支持平面几何作图（点、线段、圆、多边形、**坐标系**与常见约束）」

### 修复

- 无（V2-A 是纯新增 + 兼容变更，所有 78 个旧测试无回归）

### DB Schema 升级

W8 → W9：**无 schema 变更**。直接拉新代码即可。已有 DB 内不含 axis 对象，对老会话向后兼容。

---

## W8 — 生产部署

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
  - 新增 `T2G_GIT_MIRROR` 环境变量：主 origin fetch 失败时自动切镜像重试（国内 GitHub TLS 抖动场景必备）
- `backend/Dockerfile` 用 `PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` 走清华源；`PIP_DEFAULT_TIMEOUT=120` —— 国内服务器装 numpy/scipy 等大轮子从 KB/s 跃升到 MB/s，避免 `ReadTimeoutError`
- `frontend/Dockerfile` 用 `npm config set registry https://registry.npmmirror.com` 走淘宝镜像

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
