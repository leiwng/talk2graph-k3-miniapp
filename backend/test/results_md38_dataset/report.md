# 话图 T2G 评估报告

- **Provider**：volcengine / glm-5.2
- **Base URL**：https://ark.cn-beijing.volces.com/api/coding/v3
- **测试用例数**：38
- **求解成功**：19 / 38（50.0%）

## 分类通过率

| 类别 | 总数 | OK | 通过率 | 平均残差 | 平均延迟 |
|---|---|---|---|---|---|
| 几何图形（MVP 范围） | 15 | 15 | 100% | 8.5e-17 | 6516ms |
| 坐标系几何 | 6 | 1 | 17% | 3.5e-75 | 10857ms |
| 多轮修改 | 5 | 3 | 60% | 1.4e-30 | 16436ms |
| 函数图像（V2） | 9 | 0 | 0% | nan | 0ms |
| 统计图表（V2） | 3 | 0 | 0% | nan | 0ms |

## 详细结果

| # | 难度 | 类别 | 期望 | 状态 | 求解 | 对象 | 约束 | 残差 | 延迟 | 多轮 | 错误 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ⭐ | geometry | pass | ✅ ok | 通过 | 7 | 3 | 2.0e-31 | 6247ms | — | — |
| 2 | ⭐ | geometry | pass | ✅ ok | 通过 | 7 | 2 | 7.9e-31 | 4952ms | — | — |
| 3 | ⭐ | geometry | pass | ✅ ok | 通过 | 9 | 4 | 8.6e-59 | 5705ms | — | — |
| 4 | ⭐ | geometry | pass | ✅ ok | 通过 | 2 | — | 0.0e+00 | 5573ms | — | — |
| 5 | ⭐ | geometry | pass | ✅ ok | 通过 | 7 | 3 | 0.0e+00 | 5975ms | — | — |
| 6 | ⭐⭐ | geometry | pass | ✅ ok | 通过 | 7 | 3 | 2.0e-31 | 5872ms | — | — |
| 7 | ⭐⭐ | geometry | pass | ✅ ok | 通过 | 7 | 3 | 1.4e-64 | 6489ms | — | — |
| 8 | ⭐⭐ | geometry | best-effort | ✅ ok | 通过 | 15 | 7 | 3.9e-30 | 9052ms | — | — |
| 9 | ⭐⭐ | geometry | pass | ✅ ok | 通过 | 9 | 4 | 4.9e-32 | 5717ms | — | — |
| 10 | ⭐⭐ | geometry | pass | ✅ ok | 通过 | 9 | 5 | 2.7e-59 | 6683ms | — | — |
| 11 | ⭐⭐⭐ | geometry | pass | ✅ ok | 通过 | 7 | 3 | 3.2e-86 | 5395ms | — | — |
| 12 | ⭐⭐⭐ | geometry | pass | ✅ ok | 通过 | 9 | 3 | 1.0e-15 | 6338ms | — | — |
| 13 | ⭐⭐⭐ | geometry | best-effort | ✅ ok | 通过 | 7 | 5 | 2.6e-63 | 8011ms | — | — |
| 14 | ⭐⭐⭐ | geometry | best-effort | ✅ ok | 通过 | 11 | 6 | 4.6e-32 | 9925ms | — | — |
| 15 | ⭐⭐⭐ | geometry | pass | ✅ ok | 通过 | 9 | 1 | 2.5e-16 | 5815ms | — | — |
| 16 | ⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 本工具仅支持几何作图，不支持函数图像。请改用函数绘图工具。 |
| 17 | ⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 暂不支持函数图像绘制，仅支持几何作图（点、线段、圆、多边形等） |
| 18 | ⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 暂不支持函数图像绘制，本工具仅用于几何作图（点、线段、圆、多边形等） |
| 19 | ⭐⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | T2G 仅支持几何作图（点、线段、圆、多边形等），不支持函数图像绘制；请改用函数绘图工具。 |
| 20 | ⭐⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 本工具仅支持几何作图（点、线、多边形、圆），暂不支持函数图像绘制 |
| 21 | ⭐⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 当前 DSL 仅支持几何作图（点、线段、圆、多边形等），不支持函数图像绘制。 |
| 22 | ⭐⭐⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 本工具仅支持几何作图（点、线段、圆、多边形等），不支持函数图像绘制。 |
| 23 | ⭐⭐⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 本工具仅支持几何作图（点、线、圆、多边形等），不支持函数图像绘制 |
| 24 | ⭐⭐⭐ | function | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 当前 DSL 仅支持点、直线、线段、多边形和圆，暂不支持参数方程或椭圆等曲线 |
| 25 | ⭐ | coord | best-effort | ⚠️ llm_error | — | — | — | — | — | — | 不支持直接指定坐标；请改用边长、角度或几何约束描述（例如：三角形 ABC，AB=?, BC=?, CA=?）。 |
| 26 | ⭐⭐ | coord | best-effort | ⚠️ llm_error | — | — | — | — | — | — | 不支持直接指定坐标；请改用几何描述，例如「画线段 AB，长度为某值，标出中点 M」。 |
| 27 | ⭐⭐ | coord | best-effort | ✅ ok | 通过 | 8 | 7 | 3.5e-75 | 10857ms | — | — |
| 28 | ⭐⭐⭐ | coord | best-effort | ⚠️ llm_error | — | — | — | — | — | — | 不支持指定坐标作图；请改用边长、角度等几何约束描述（如 AB=4、BC=√13、CA=√13），我可以画出三角形、三边中 |
| 29 | ⭐⭐⭐ | coord | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 暂不支持抛物线等曲线方程作图，仅支持直线、线段、多边形与圆的几何约束作图 |
| 30 | ⭐⭐⭐ | coord | best-effort | ⚠️ llm_error | — | — | — | — | — | — | 不支持直接给定坐标作图；请改用几何关系描述，例如『画直线 l，点 A 在 l 外，作 A 关于 l 的对称点 A′』。 |
| 31 | ⭐ | chart | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 本工具仅支持几何作图，柱状图等统计图表请使用其他工具 |
| 32 | ⭐ | chart | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 饼图属于统计图表，不在几何作图 DSL 支持范围内 |
| 33 | ⭐⭐ | chart | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 频率分布直方图属于统计图表，不在几何作图 DSL 支持范围内 |
| 34 | ⭐⭐⭐ | multi-round | pass | ✅ ok | 通过 | 7 | 3 | 2.0e-31 | 11177ms | ok patch (6 ops, res=2.7e-70) | — |
| 35 | ⭐⭐⭐ | multi-round | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 当前 DSL 仅支持几何作图（点、线段、圆、多边形等），暂不支持函数图像绘制 |
| 36 | ⭐⭐⭐ | multi-round | pass | ✅ ok | 通过 | 7 | 3 | 0.0e+00 | 11966ms | ok patch (6 ops, res=1.1e-62) | — |
| 37 | ⭐⭐⭐ | multi-round | best-effort | ✅ ok | 通过 | 15 | 7 | 3.9e-30 | 26167ms | ok patch (11 ops, res=1.7e-29) | — |
| 38 | ⭐⭐⭐ | multi-round | unsupported | ⚠️ llm_error | — | — | — | — | — | — | 暂不支持函数图像绘制，本工具仅支持几何作图（点、线段、圆、多边形） |

## 渲染产物

成功用例的 SVG 文件保存在 `test/results/svgs/`：
- `case_01.svg` — 画一个直角三角形，两条直角边分别是 3 和 4
- `case_02.svg` — 画一个等边三角形，边长 5cm
- `case_03.svg` — 画一个正方形，边长 4cm
- `case_04.svg` — 画一个圆，半径 3cm，标注圆心
- `case_05.svg` — 画一个等腰三角形，底边长 6cm，腰长 5cm
- `case_06.svg` — 画直角三角形，直角边 3 和 4，标出三条边的边长和直角标记
- `case_07.svg` — 画一个底角为 30° 的等腰三角形，腰长 5cm，标出顶角和底角
- `case_08.svg` — 画一个圆，内接一个正六边形，标注圆心
- `case_09.svg` — 画一个平行四边形，相邻两边分别为 4cm 和 3cm，夹角 60°
- `case_10.svg` — 画直角梯形，上底 3cm，下底 5cm，高 4cm
- `case_11.svg` — 画一个三角形，已知 AB=5，BC=6，AC=7，标出各边长度
- `case_12.svg` — 画直角三角形的内切圆，直角边分别为 3 和 4，标出内切圆圆心和半径
- `case_13.svg` — 画两个相交的圆，半径分别为 3cm 和 4cm，圆心距 5cm，标注两个交点和圆
- `case_14.svg` — 画一个正五边形，边长 3cm，标出所有顶点
- `case_15.svg` — 画一个三角形 ABC，在 AB 边上取中点 D，连接 CD，标注 D 和中线
- `case_27.svg` — 在坐标系中画以原点为圆心、半径为 5 的圆，标出与坐标轴的四个交点
- `case_34.svg` + 第二轮 — 画一个直角三角形，直角边 3 和 4
- `case_36.svg` + 第二轮 — 画等腰三角形，底 6cm，腰 5cm
- `case_37.svg` + 第二轮 — 画一个圆，内接正六边形