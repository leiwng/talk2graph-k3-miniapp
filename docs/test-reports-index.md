# 话图 T2G · 测试报告全索引 (v0.13.1)

> 汇总所有历史测试报告：每次评估都会写入 `backend/test/results_*/` 目录，含 `report.md`（可读）+ `results.json`（机器可读）+ `svgs/*.svg`（成功题的图）。

## 一览表

| 目录 | 数据集 | 版本 | 题量 | ok | SVG | 报告日期 |
|---|---|---|---|---|---|---|
| **results_chengdu_full** ⭐ | chengdu_full 68 题 | **v0.13.1**（最新） | 68 | **48** | 56 | 2026-07-02 |
| results_chengdu_full_v0.13.0_baseline | chengdu_full | v0.13.0（W13-A 后） | 68 | 48 | 53 | 2026-07-02 |
| results_chengdu_full_v0.12.1_baseline | chengdu_full | v0.12.1（W13 前） | 68 | 41 | 41 | 2026-07-02 |
| results_chengdu | chengdu_selected 20 题 | v0.12.1 | 20 | 18 | 18 | 2026-07-01 |
| results_chengdu_v0.12.0_baseline | chengdu_selected | v0.12.0（W12 前） | 20 | 17 | 35 | 2026-07-01 |
| **results_cmm_v2r** | cmm v2r 56 题 | v0.12.1（W12 后） | 56 | 36 | 42 | 2026-07-01 |
| results_cmm_v2r_w11_baseline | cmm v2r | v0.11.0（W11） | 56 | 34 | 40 | 2026-07-01 |
| results_cmm_v2r_w10_baseline | cmm v2r | v0.10.0（W10） | 56 | 35 | 39 | 2026-07-01 |
| results_cmm_v2r_w9_baseline | cmm v2r | v0.9.0（W9） | 56 | 36 | 39 | 2026-06-30 |
| results_cmm_v2r_w8_baseline | cmm v2r | v0.8.0（W8） | 56 | 38 | 38 | 2026-06-30 |
| results_cmm_v1 | cmm v1 原题（含 LaTeX） | 早期 | 56 | 39 | 39 | 2026-06-26 |
| results_md38_dataset | 早期 38 题集（已废弃） | v0.6.0 前 | - | - | 22 | 2026-06-26 |

外加一份 **`results_v1_v2r_comparison.md`**：v1 原题 vs v2r 改写后的 A/B 对比分析。

---

## 每个报告目录的内容

统一结构：
```
results_XXX/
├── report.md         # 可读评估报告（含分组表 + 失败详情 + 每题结果）
├── results.json      # 机器可读结果（每题含 dsl_json, residual, latency_ms 等）
└── svgs/
    └── *.svg         # 求解成功题的 SVG 输出
```

---

## 主评估集轨迹 · chengdu_full 68 题

| 版本 | 通过率 | 符合预期率 | 关键变更 |
|---|---|---|---|
| v0.12.1（W12 后） | 41/68 (60.3%) | 42/68 (61.8%) | 首次全量评估基线 |
| v0.13.0（W13-A 后） | **48/68 (70.6%)** ⬆️+7 | 47/68 (69.1%) | 求解器自适应重启 |
| v0.13.1（W13-B 后，当前）| 48/68 (70.6%) | **52/68 (76.5%)** ⬆️+5 | LLM 二次修复回路 + 歧义处理 |

- v0.12.1 → v0.13.1 累计：**通过率 +7 题、符合预期率 +10 题**
- 详细分析：`docs/eval-v0.12.1-chengdu-full.md`

## 精选集轨迹 · chengdu_selected 20 题

| 版本 | 通过率 | 符合预期率 |
|---|---|---|
| v0.12.0（V2-B 后） | 17/20 (85%) | 18/20 (90%) |
| v0.12.1（W12 后）| **18/20 (90%)** ⬆️+1 | **20/20 (100%)** |

## cmm v2r 轨迹 · 56 题（早期评估集）

| 版本 | 通过率 | 变化 |
|---|---|---|
| W8 基线 | **38/56 (68%)** ⭐ 最高 | - |
| W9 后 | 36/56 (64%) | -2 |
| W10 后 | 35/56 (63%) | -1 |
| W11 后 | 34/56 (61%) | -1 |
| W12/V2-B 后（当前） | 36/56 (64%) | +2 |

**注**：cmm v2r 略微退化的题多是 **LLM 输出漂移**（同一题不同轮次答不同）或 **LLM 判断更严谨**（原本 ok 但含歧义题被主动 refuse），非代码回归。这类波动在真题库上更小（因为真题结构清晰）。

---

## 快速查看命令

### 看当前最新主评估 report
```bash
open backend/test/results_chengdu_full/report.md
# 或
cat backend/test/results_chengdu_full/report.md | less
```

### 逐题对比两个版本（W13-A vs W13-B）
```bash
jq -r '.[] | "\(.id)|\(.status)"' backend/test/results_chengdu_full_v0.13.0_baseline/results.json > /tmp/before.txt
jq -r '.[] | "\(.id)|\(.status)"' backend/test/results_chengdu_full/results.json > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt
```

### 看某题的 SVG
```bash
open backend/test/results_chengdu_full/svgs/zk_007.svg  # 用浏览器打开
```

### 看某题的 LLM DSL 输出（含 residual、约束）
```bash
jq -r '.[] | select(.id=="zk_007") | .dsl_json' backend/test/results_chengdu_full/results.json | jq
```

### 看某个报告的分组统计
```bash
head -50 backend/test/results_chengdu_full/report.md
```

---

## 报告 report.md 里的关键区块

打开任一 `report.md`，从上到下会看到：

1. **头部指标**：Provider、题量、通过率、符合预期率、平均延迟、平均残差
2. **按题型分组**：平面几何 / 几何变换 / 函数图像 / 坐标系 / 立体几何 / 统计图表 的通过率
3. **按来源分组**：中考各卷 / 高考卷 的通过率
4. **失败题详情**：
   - solve_fail 列表（每题 nl + 期望 + 错误 + obj/con 数）
   - 意外拒绝（期望 ok 但 LLM 拒绝了）
   - partial 类拒绝
   - 合理拒绝（期望和实际均为 refuse）
5. **逐题结果表**：每题 ID / 来源 / 类型 / 期望 / 实际 / obj / con / 残差 / 延迟
6. **详情区**：每题的 NL + 期望/实际 + LLM 拒绝理由（若有）

---

## 有价值的历史对比文档

除了 `results_*/report.md`，另有：

| 文档 | 用途 |
|---|---|
| `docs/eval-v0.12.1-chengdu-full.md` | 首次成都 68 题全量评估的深度分析（5 大洞察 + W13 三候选方向） |
| `backend/test/results_v1_v2r_comparison.md` | cmm v1 原题 vs v2r 改写的 A/B 对比 |
| `docs/audit-worksheet-v0.12.1.md` | 73 候选题人工审核工作表（生成 chengdu_full.json 时用） |

---

## 磁盘占用（供参考）

| 目录 | 大小 |
|---|---|
| results_chengdu_v0.12.0_baseline | 1.1 MB |
| results_chengdu_full | 540 KB |
| results_chengdu_full_v0.13.0_baseline | 524 KB |
| results_chengdu_full_v0.12.1_baseline | 472 KB |
| results_cmm_v2r_* 系列（5 个） | 各 ~200 KB |
| **合计** | ~4 MB |

全部通过 git 版本化，未来任意时刻可以回溯或做 A/B 对比。
