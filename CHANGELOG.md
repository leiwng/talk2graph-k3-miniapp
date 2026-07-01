# 变更日志

> 持续记录每个里程碑的关键变更，便于下一轮对话/接手时快速理解上下文。

格式约定：每个版本块包含「新增 / 变更 / 修复」与对应模块。

---

## W12 — on_curve 硬约束 + 求解器 hint 残差分离（当前版本）

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
