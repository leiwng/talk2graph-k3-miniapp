# 话图 T2G · 测试集完整清单 (v0.13.1)

> 汇总当前话图项目里所有测试数据集，含来源、规模、字段结构、使用方式。

## 一览

| 类别 | 数据集 | 题量 | 用途 | 位置 |
|---|---|---|---|---|
| **A. 端到端评估集** | | | 跑 LLM + 求解 + 渲染全链路 | |
| A1 | `chengdu_full.json` ⭐ | **68** | 主评估集（W13-B 基线：48/68 ok，52/68 符合预期 76.5%）| `backend/test/chengdu/` |
| A2 | `chengdu_selected.json` | **20** | 精选集（早期快速回归，18/20 ok 90%）| `backend/test/chengdu/` |
| A3 | `cmm_test_v1_original.json` | **56** | 全国合集原题（含 LaTeX 公式）| `test/`（repo 根）|
| A4 | `cmm_test_v2_rewritten.json` | **56** | v1 改写后（明确作图指令）| `test/`（repo 根）|
| **B. 抽题候选** | | | 半成品，用于扩集 / 溯源 | |
| B1 | `candidates_2021_zhongkao.json` | 71 作图题 / 169 段 | 2021 中考 10 卷 LLM 抽题输出 | `backend/test/chengdu/` |
| B2 | `candidates_2025_gaokao.json` | 2 作图题 / 4 段 | 2025 高考 LLM 抽题输出 | `backend/test/chengdu/` |
| **C. 单元测试** | | | 求解器 / 渲染器 / DSL 正确性 | |
| C1 | `tests/test_*.py`（15 个文件）| 149 测试 | pytest 单元测试全集 | `backend/tests/` |

---

## A1 · chengdu_full.json（主评估集，68 题）⭐

**来源**：从 2021 全国中考 10 卷合集 + 2025 新课标II高考卷 LLM 辅助抽取 + 人工审核后得到。

**字段结构**：
```json
{
  "id": "zk_001",              // 唯一 ID (zk_/gk_ + 3 位序号)
  "source": "2021 中考",        // 来源标签
  "q_num": "3",                 // PDF 中原题号
  "type": "平面几何",           // 类型分类
  "expected": "ok",             // 期望结果: ok / partial / refuse
  "confidence": "high",         // LLM 抽取置信度
  "nl": "画...",                // 自然语言作图指令
  "notes": ""                   // 备注（可选）
}
```

**分布**：

| 维度 | 分组 | 数量 |
|---|---|---|
| **type** | 平面几何 | 50 |
| | 几何变换 | 8 |
| | 坐标系 | 4 |
| | 函数图像 | 4 |
| | 立体几何 | 1 |
| | 统计图表 | 1 |
| **expected** | ok（能画） | 52 |
| | partial（部分能画） | 10 |
| | refuse（应拒绝） | 6 |
| **source** | 2021 中考 | 66 |
| | 2025 高考·新课标II | 2 |

**使用方式**：
```bash
cd backend
.venv/bin/python scripts/eval_chengdu.py \
    --dataset test/chengdu/chengdu_full.json \
    --out test/results_chengdu_full \
    --concurrency 2
```

**基线成绩**（v0.13.1, 火山方舟 GLM-5.2）：
- 求解成功 48/68 (70.6%)
- 符合预期 52/68 (76.5%)
- 平均延迟 26s、平均残差 1e-6

---

## A2 · chengdu_selected.json（精选集，20 题）

**来源**：早期人工从话图目标场景挑选，含基础/中等/较难 3 档中考题 + 4 道 2025 高考题。

**字段结构**（与 A1 略有不同，早期版本）：
```json
{
  "id": "zk_easy_01",           // ID 格式为 zk_easy/med/hard_NN 或 gk_hard_NN
  "source": "2021 中考·基础",
  "type": "平面几何·垂直",     // 更细粒度的类型
  "expected": "ok",
  "nl": "画..."
}
```

**分布**：

| 维度 | 分组 | 数量 |
|---|---|---|
| **难度** | 基础 | 7 |
| | 中等 | 6 |
| | 较难（中考）| 3 |
| | 较难（高考）| 4 |
| **expected** | ok | 15 |
| | partial | 3 |
| | refuse | 2 |

**用途**：作为**快速回归集**（每次改动 solver / prompt 后跑一遍确认无退化）。20 题跑完约 90 秒。

**基线成绩**（v0.12.1）：
- 求解成功 18/20 (90%)
- 符合预期 20/20 (100%)

---

## A3 · A4 · cmm_test_v1/v2r（56 题）

**来源**：早期用于开发和评估的**全国范围**题库。

- **v1_original**：原题（含大量 LaTeX 公式 `\angle`、`\overline`、`\qquad`）
- **v2_rewritten**：用 LLM 把 v1 改写成"明确作图指令"，去掉 LaTeX

**字段结构**（v2r）：
```json
{
  "id": 22586,
  "subject": "度量几何学",       // 6 分类：解析/度量/组合/立体/画法/变换
  "difficulty": "中等",
  "original_description": "...", // v1 原文
  "rewritten": "画..."           // v2 改写后
}
```

**分布**（v2r 56 题）：

| subject | 数量 |
|---|---|
| 解析几何 | 16 |
| 度量几何学 | 15 |
| 组合几何学 | 10 |
| 立体几何学 | 7 |
| 画法几何学 | 4 |
| 变换几何 | 4 |

**使用方式**：
```bash
cd backend
.venv/bin/python scripts/eval_cmm.py v2r --concurrency 4
```

**基线成绩**（v0.12.1）：36/56 (64.3%)

---

## B1 · B2 · candidates_*.json（抽题候选，半成品）

**来源**：`scripts/build_dataset_from_pdf.py` 处理原始 PDF 后 LLM 抽取的粗筛结果，**未经人工审核**。

**字段结构**：
```json
{
  "tag": "2021 中考",
  "q_num": "5",
  "raw_text": "题目原文（前 500 字符）",
  "is_drawing_task": true,
  "nl": "画...",
  "type": "平面几何",
  "expected": "ok",
  "confidence": "high",
  "notes": "",
  "reason": "",                // 非作图题的原因
  "llm_error": ""              // LLM 调用异常信息
}
```

**用途**：
- 溯源：查看某题的原始出处
- 扩集：如需要增加数据集大小，从候选里再筛
- 复现：脚本可重跑，每次输出稳定

**规模**：
- 2021 中考：从 258 段候选 → 169 段含作图关键词 → 71 作图题
- 2025 高考：从 15 段候选 → 4 段 → 2 作图题

---

## C · pytest 单元测试（149 测试）

**位置**：`backend/tests/`

**分类**（按里程碑）：

| 文件 | 测试数 | 覆盖能力 |
|---|---|---|
| `test_w1_endtoend.py` | 5 | DSL + 求解器 + SVG 渲染基础 |
| `test_w2_llm.py` | 9 | LLM 抽取 + few-shot 全部可解 |
| `test_w3_api.py` | 12 | DSL diff + 会话 + API 端到端 |
| `test_w5_geometry.py` | 9 | 中点/垂足/角平分线/共圆/平行四边形 |
| `test_w6_ops.py` | 10 | 错误分类、admin 接口 |
| `test_w6_stress.py` | 20 | 压测题 |
| `test_w7_feedback.py` | 11 | 反馈机制 + 拒绝分类 |
| `test_w9_axis.py` | 11 | 坐标系（axis 对象）|
| `test_w10_halfplane.py` | 10 | same_side / opposite_side + 隐藏辅助点 |
| `test_w10_fallback.py` | 4 | patch fallback + DB 自动迁移 |
| `test_w11_transform.py` | 14 | 4 种几何变换 + 派生对象 |
| `test_v2b_curve.py` | 19 | 函数曲线 + AST 安全沙箱 |
| `test_w12_on_curve.py` | 7 | on_curve 硬约束 |
| `test_w13_adaptive_restarts.py` | 4 | 求解器自适应重启 |
| `test_w13b_solve_repair.py` | 4 | 约束诊断 + LLM 二次修复 |
| **合计** | **149** | |

**使用方式**：
```bash
cd backend && .venv/bin/pytest -q
# 期望：149 passed
```

---

## D · 评估结果目录（每次跑评估的产物）

**当前保留的评估结果**：

| 目录 | 版本对应 | 用途 |
|---|---|---|
| `results_chengdu/` | v0.12.1（20 题） | 精选集最新结果 |
| `results_chengdu_v0.12.0_baseline/` | v0.12.0 | 20 题 W12 前基线 |
| **`results_chengdu_full/`** | **v0.13.1（68 题）** | **主评估集最新结果** |
| `results_chengdu_full_v0.12.1_baseline/` | v0.12.1 | 68 题 W13 前基线 |
| `results_chengdu_full_v0.13.0_baseline/` | v0.13.0 | 68 题 W13-A 后（B 前） |
| `results_cmm_v1/` | 各版本 | cmm v1 结果 |
| `results_cmm_v2r/` | v0.12.1 | cmm v2r 结果 |
| `results_cmm_v2r_w8/9/10/11_baseline/` | 历史 | cmm 逐版本基线 |
| `results_md38_dataset/` | 早期 | 已废弃早期 38 题集 |

每个结果目录含：
- `report.md`：可读评估报告（含分组表 + 失败详情）
- `results.json`：机器可读结果（含每题 dsl_json + residual + latency）
- `svgs/*.svg`：成功题的 SVG 输出图

---

## E · 抽题相关脚本（可复用）

| 脚本 | 用途 |
|---|---|
| `scripts/build_dataset_from_pdf.py` | 从 PDF 提取 → 分段 → LLM 抽题 → 生成候选 JSON |
| `scripts/extract_prompt.txt` | LLM 抽题专用 prompt |
| `scripts/build_audit_worksheet.py` | 候选 → 审核工作表（人工审核用）|
| `scripts/build_final_dataset.py` | 审核后候选 → 最终 chengdu_full.json |
| `scripts/eval_chengdu.py` | 跑评估 + 生成 report |
| `scripts/eval_cmm.py` | 跑 cmm 数据集评估 |
| `scripts/rewrite_v2.py` | 把 v1 原题改写为 v2r（LLM 辅助）|
| `scripts/compare_v1_v2r.py` | v1 vs v2r 对比 |

---

## F · 未整合的原始素材（在项目 iCloud 目录外）

**位置**：`/Users/leiwng/Library/Mobile Documents/com~apple~CloudDocs/__NEW/00_MINE/PRJ/话图/`

| 文件 | 状态 | 备注 |
|---|---|---|
| 中考/2021中考数学真题_网易.pdf | ✅ 已抽取 | 71 作图题 |
| 高考/2025新课标II卷数学_解析.pdf | ✅ 已抽取 | 2 作图题 |
| 高考/2021全国甲卷理科数学_北京高考在线.pdf | ⚠️ 未抽取 | 可扩展 |
| 中考/其他 5 个 .txt | ❌ HTML 网页壳 | 题目在图片里，无法提取 |
| 高考/其他 6 个 .txt | ❌ HTML 网页壳 | 同上 |

如果未来要扩集，只有 **2021 全国甲卷 PDF** 能通过现有抽题脚本自动处理。其它 .txt 是网页 HTML，实际题目在图片里，需要 OCR 或人工重录。

---

## 快速使用手册

### 场景 1：改了 solver / prompt，快速验证不退化
```bash
cd backend && .venv/bin/pytest -q      # 单元测试 149 项 1 秒
```

### 场景 2：做完新里程碑，评估真题通过率
```bash
cd backend
.venv/bin/python scripts/eval_chengdu.py \
    --dataset test/chengdu/chengdu_full.json \
    --out test/results_chengdu_full \
    --concurrency 2
# 约 15 分钟出结果，看 report.md
```

### 场景 3：小改动快速回归（不想等 15 分钟）
```bash
cd backend
.venv/bin/python scripts/eval_chengdu.py \
    --dataset test/chengdu/chengdu_selected.json \
    --out test/results_chengdu \
    --concurrency 4
# 约 90 秒
```

### 场景 4：扩集（收集了新 PDF）
```bash
cd backend
.venv/bin/python scripts/build_dataset_from_pdf.py \
    --pdf "path/to/new.pdf" \
    --tag "2024 中考·XX" \
    --out test/chengdu/candidates_new.json

.venv/bin/python scripts/build_audit_worksheet.py
# 打开 docs/audit-worksheet-*.md 人工审核

.venv/bin/python scripts/build_final_dataset.py
# 更新 chengdu_full.json
```
