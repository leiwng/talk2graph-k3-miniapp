# 多 Provider 对比评测报告

- **数据集**：chengdu_full.json
- **题数**：68
- **Provider 数**：8
- **生成时间**：2026-07-07 19:25:08

## 表 1 · 总览对比

| Provider | Model | OK | 符合预期 | 通过率 | 平均残差 | p50 延迟 | p95 延迟 | 调用次数 | 输入 tokens | 输出 tokens | 估算成本(元) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `volcengine` | glm-5.2 | 35 | 37 | 51.5% | 2.3e-06 | 111.2s | 180.6s | 122 | 528,729 | 134,260 | 0.466 |
| `deepseek` | deepseek-v4-flash | 42 | 50 | 61.8% | 9.6e-08 | 30.6s | 116.7s | 109 | 971,374 | 239,537 | 0.845 |
| `minimax` | MiniMax-M3 | 41 | 52 | 60.3% | 2.2e-06 | 9.4s | 179.5s | 103 | 835,072 | 82,012 | 0.541 |
| `volcengine_doubao_pro` | Doubao-Seed-2.0-pro | 56 | 56 | 82.4% | 2.0e-06 | 54.7s | 174.3s | 110 | 782,179 | 259,225 | 1.144 |
| `deepseek_v4_pro` | deepseek-v4-pro | 44 | 47 | 64.7% | 1.3e-06 | 55.7s | 210.1s | 109 | 900,357 | 222,707 | 3.582 |
| `kimi_k26` | kimi-k2.6 | 47 | 57 | 69.1% | 8.2e-07 | 19.4s | 72.1s | 102 | 905,516 | 47,654 | 1.096 |
| `kimi_k27_code` | kimi-k2.7-code | 36 | 39 | 52.9% | 1.3e-06 | 114.0s | 180.6s | 122 | 570,395 | 105,010 | 0.990 |
| `kimi_k27_code_hs` | kimi-k2.7-code-highspeed | 33 | 38 | 48.5% | 9.0e-10 | 17.5s | 32.0s | 105 | 707,344 | 200,875 | 0.655 |

## 表 2 · 逐题状态对比

| ID | 类型 | 期望 | `volcengine` | `deepseek` | `minimax` | `volcengine_doubao_pro` | `deepseek_v4_pro` | `kimi_k26` | `kimi_k27_code` | `kimi_k27_code_hs` |
|---|---|---|---|---|---|---|---|---|---|---|
| zk_001 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_002 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_003 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | 🔴 | ✅ | ✅ | ✅ |
| zk_004 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ |
| zk_005 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_006 | 几何变换 | ok | ✅ | ✅ | 🔴 | ✅ | ✅ | 🟡 | ✅ | ⚠️ |
| zk_007 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 | ⚠️ | ✅ |
| zk_008 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 | ✅ |
| zk_009 | 坐标系 | partial | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_010 | 几何变换 | ok | 🔴 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_011 | 平面几何 | ok | ✅ | 🔴 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_012 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 | ✅ |
| zk_013 | 函数图像 | partial | ⚠️ | ✅ | 🟡 | ✅ | 🔴 | ✅ | 🔴 | ✅ |
| zk_014 | 平面几何 | ok | ✅ | 🔴 | ✅ | ✅ | ✅ | ✅ | 🔴 | ✅ |
| zk_015 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| zk_016 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_017 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_018 | 几何变换 | refuse | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| zk_019 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_020 | 平面几何 | ok | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| zk_021 | 平面几何 | ok | ⚠️ | ✅ | 🔴 | 🔴 | 🔴 | ✅ | ⚠️ | ⚠️ |
| zk_022 | 几何变换 | ok | 🔴 | 🔴 | 🔴 | 🔴 | ✅ | ✅ | ✅ | ⚠️ |
| zk_023 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_024 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ |
| zk_025 | 几何变换 | ok | ⚠️ | 🟡 | ✅ | ✅ | 🟡 | 🟡 | ⚠️ | ⚠️ |
| zk_026 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_027 | 平面几何 | partial | ⚠️ | 🔴 | ⚠️ | 🔴 | 🔴 | ✅ | ✅ | ✅ |
| zk_028 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_029 | 平面几何 | ok | ⚠️ | 🔴 | ✅ | 🔴 | 🔴 | ✅ | ⚠️ | ✅ |
| zk_030 | 平面几何 | partial | ⚠️ | ✅ | 🟡 | ✅ | ✅ | 🟡 | ⚠️ | ⚠️ |
| zk_031 | 几何变换 | partial | ⚠️ | 🟡 | 🟡 | ✅ | 🟡 | 🟡 | ⚠️ | ⚠️ |
| zk_032 | 坐标系 | refuse | 🟡 | 🟡 | 🟡 | ✅ | 🟡 | 🟡 | 🟡 | 🟡 |
| zk_033 | 平面几何 | ok | ✅ | ✅ | 🟡 | ✅ | 🟡 | 🔴 | ⚠️ | 🔴 |
| zk_034 | 平面几何 | ok | 🟡 | 🟡 | ✅ | ✅ | 🔴 | 🟡 | 🟡 | 🟡 |
| zk_035 | 平面几何 | ok | 🔴 | 🔴 | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_036 | 平面几何 | ok | ✅ | ✅ | 🔴 | ✅ | 🟡 | ✅ | ✅ | ✅ |
| zk_037 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_038 | 平面几何 | ok | 🔴 | ✅ | ✅ | 🔴 | 🔴 | ✅ | ⚠️ | ⚠️ |
| zk_039 | 平面几何 | ok | ✅ | 🔴 | 🟡 | ✅ | 🔴 | ✅ | ✅ | ⚠️ |
| zk_040 | 平面几何 | partial | ⚠️ | ✅ | 🟡 | ✅ | ✅ | 🟡 | ⚠️ | ⚠️ |
| zk_041 | 平面几何 | ok | ⚠️ | 🔴 | ✅ | 🔴 | ✅ | ✅ | ⚠️ | ⚠️ |
| zk_042 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_043 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔴 |
| zk_044 | 平面几何 | ok | ✅ | 🟡 | 🟡 | ✅ | 🟡 | ✅ | 🟡 | ⚠️ |
| zk_045 | 平面几何 | ok | ⚠️ | ✅ | 🟡 | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| zk_046 | 统计图表 | refuse | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| zk_047 | 几何变换 | ok | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_048 | 坐标系 | ok | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| zk_049 | 平面几何 | ok | 🔴 | 🔴 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| zk_050 | 平面几何 | ok | 🔴 | ✅ | ✅ | ✅ | 🔴 | 🔴 | ✅ | ⚠️ |
| zk_051 | 平面几何 | ok | ✅ | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_052 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_053 | 函数图像 | refuse | ⚠️ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ⚠️ |
| zk_054 | 坐标系 | partial | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| zk_055 | 平面几何 | ok | ✅ | 🔴 | ✅ | 🔴 | 🔴 | ✅ | ⚠️ | 🔴 |
| zk_056 | 平面几何 | ok | ⚠️ | ✅ | 🔴 | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| zk_057 | 平面几何 | ok | ⚠️ | ✅ | ⚠️ | 🔴 | ✅ | 🔴 | ⚠️ | ⚠️ |
| zk_058 | 平面几何 | ok | ⚠️ | 🟡 | ✅ | ✅ | 🔴 | ✅ | ⚠️ | ⚠️ |
| zk_059 | 平面几何 | ok | 🔴 | 🔴 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_060 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| zk_061 | 平面几何 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| zk_062 | 函数图像 | partial | ⚠️ | 🟡 | 🟡 | ✅ | ✅ | 🟡 | ⚠️ | ⚠️ |
| zk_063 | 平面几何 | ok | ✅ | 🟡 | ✅ | ✅ | 🟡 | ✅ | ✅ | 🟡 |
| zk_064 | 几何变换 | partial | ✅ | ✅ | ⚠️ | ✅ | 🔴 | ✅ | 🔴 | ⚠️ |
| zk_065 | 立体几何 | refuse | ✅ | 🟡 | 🟡 | ✅ | ✅ | 🟡 | ✅ | 🟡 |
| zk_066 | 平面几何 | ok | ⚠️ | 🔴 | 🟡 | ✅ | 🟡 | 🔴 | ⚠️ | ✅ |
| gk_001 | 函数图像 | partial | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| gk_002 | 平面几何 | refuse | ⚠️ | 🟡 | 🟡 | ✅ | ✅ | 🟡 | ⚠️ | 🟡 |

## 表 3 · 失败题详情

（仅展示至少一家 provider 失败的题）

| ID | NL（前 60 字） | 类型 | 期望 | `volcengine` | `deepseek` | `minimax` | `volcengine_doubao_pro` | `deepseek_v4_pro` | `kimi_k26` | `kimi_k27_code` | `kimi_k27_code_hs` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| zk_003 | 画圆 O，点 A、B、C 在圆 O 上，连接 OB、OC、AB、AC，标注 ∠BAC=54° | 平面几何 | ok | ok | ok | ok | ok | solve_fail | ok | ok | ok |
| zk_004 | 画长方形 ABCD，AB=4，AD=3，以 B 为圆心作半径为 1 的圆，以 A 为圆心作与圆 B 内切的圆 | 平面几何 | ok | ok | ok | ok | ok | ok | llm_refuse | ok | ok |
| zk_006 | 画平行四边形 ABCD，将△ABC 沿 AC 折叠得到△AB'C，B'C 交 AD 于 E，连接 B'D，其中 ∠B=6 | 几何变换 | ok | ok | ok | solve_fail | ok | ok | llm_refuse | ok | llm_error |
| zk_007 | 画正方形 ABCD，AB=2，E 是 BC 中点，在 BC 延长线上取点 F 使 EF=ED，过 F 作 FG⊥ED，交 | 平面几何 | ok | ok | ok | ok | ok | ok | solve_fail | llm_error | ok |
| zk_008 | 画正六边形 ABCDEF，连接对角线 FD，在 FD 上取一点 O，连接 AO、CO | 平面几何 | ok | ok | ok | ok | ok | ok | ok | solve_fail | ok |
| zk_010 | 画两条相交于点 O 的直线 l 和 m，取直线外一点 P，OP=2.8，作 P 关于 l 的对称点 P1 和关于 m 的 | 几何变换 | ok | solve_fail | ok | ok | ok | ok | ok | ok | ok |
| zk_011 | 画圆 O，弦 AB 长为 4，圆心 O 到弦 AB 的距离为 2 | 平面几何 | ok | ok | solve_fail | ok | ok | ok | ok | ok | ok |
| zk_012 | 画圆 O，AB 是弦，C 是弧 AB 的中点，OC 交 AB 于点 D，AB=8，CD=2 | 平面几何 | ok | ok | ok | ok | ok | ok | ok | solve_fail | ok |
| zk_013 | 画正比例函数 y=kx 与反比例函数 y=k/x 的图象，交于 A、B 两点，过 B 作 BC 平行于 x 轴，过 A  | 函数图像 | partial | llm_error | ok | llm_refuse | ok | solve_fail | ok | solve_fail | ok |
| zk_014 | 画圆 O，PA、PB 是圆 O 的两条切线，A、B 是切点，标出 ∠P=50° | 平面几何 | ok | ok | solve_fail | ok | ok | ok | ok | solve_fail | ok |
| zk_015 | 画∠BAC=60°，AD是∠BAC的角平分线且AD=10，作AD的垂直平分线交AC于F，过D作DE⊥AC于E | 平面几何 | ok | ok | ok | ok | ok | ok | ok | ok | llm_error |
| zk_018 | 画反比例函数图像过 A、B 两点，A 坐标为 (2,3)，直线 AB 过原点交反比例函数于 A、B，将线段 AB 绕点  | 几何变换 | refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse |
| zk_020 | 画一条自西向东的射线 BC，BC=12，在 B 点北偏东 60° 方向、C 点北偏东 30° 方向确定小岛 A，作 A  | 平面几何 | ok | llm_error | ok | ok | ok | ok | ok | llm_error | llm_error |
| zk_021 | 画五边形 ABCDE 及其外接圆，FA、GB、HC、ID、JE 分别是过 A、B、C、D、E 的切线 | 平面几何 | ok | llm_error | ok | solve_fail | solve_fail | solve_fail | ok | llm_error | llm_error |
| zk_022 | 画三角形 ABC，D、E 分别在 BC、AC 上，将三角形 CDE 沿 DE 翻折得到三角形 FDE，连接 BF、CF， | 几何变换 | ok | solve_fail | solve_fail | solve_fail | solve_fail | ok | ok | ok | llm_error |
| zk_024 | 画四边形 ABCD，其中 AB=BD=BC，∠ABC=α | 平面几何 | ok | ok | ok | ok | ok | ok | llm_refuse | ok | ok |
| zk_025 | 画平行四边形 ABCD，AB=3，BC=4，将其绕点 A 逆时针旋转得到平行四边形 A'B'C'D'，使 B' 落在 B | 几何变换 | ok | llm_error | llm_refuse | ok | ok | llm_refuse | llm_refuse | llm_error | llm_error |
| zk_027 | 画等腰三角形 AOB，顶角∠AOB=40°，以 O 为圆心 OA 为半径作圆，在圆上取一点 P，连接 AP，作 AB 的 | 平面几何 | partial | llm_error | solve_fail | llm_error | solve_fail | solve_fail | ok | ok | ok |
| zk_029 | 画菱形 ABCD，∠ABC=70°，延长 BC 到 E，在 ∠DCE 内作射线 CM 使 ∠ECM=15°，过 D 作  | 平面几何 | ok | llm_error | solve_fail | ok | solve_fail | solve_fail | ok | llm_error | ok |
| zk_030 | 画六个含30度角的直角三角板拼成的正六边形，其中直角三角板的最短边为1 | 平面几何 | partial | llm_error | ok | llm_refuse | ok | ok | llm_refuse | llm_error | llm_error |
| zk_031 | 画互相垂直的射线 OM、ON，在 OM 上取点 A 使 OA=8，作 OA 的垂直平分线 l，在 l 上（OM 上方）取 | 几何变换 | partial | llm_error | llm_refuse | llm_refuse | ok | llm_refuse | llm_refuse | llm_error | llm_error |
| zk_032 | 画大、小两个正方形，中心均与平面直角坐标系原点O重合，边与坐标轴平行，反比例函数 y=k/x 的图象与大正方形的一边交于 | 坐标系 | refuse | llm_refuse | llm_refuse | llm_refuse | ok | llm_refuse | llm_refuse | llm_refuse | llm_refuse |
| zk_033 | 画 AB∥CD，∠B=∠D，直线 EF 分别交 AD、BC 的延长线于点 E、F | 平面几何 | ok | ok | ok | llm_refuse | ok | llm_refuse | solve_fail | llm_error | solve_fail |
| zk_034 | 画圆 O 及其弦 AB，D、C 为弧 ACB 的三等分点，连接 AC、BC、BE，AC∥BE | 平面几何 | ok | llm_refuse | llm_refuse | ok | ok | solve_fail | llm_refuse | llm_refuse | llm_refuse |
| zk_035 | 画测量点 A 与佛像底部 D 在同一水平线上，佛像 BD 垂直于地面，头部为 BC=4m，从 A 观测 B 的仰角为 4 | 平面几何 | ok | solve_fail | solve_fail | llm_refuse | ok | ok | ok | ok | ok |
| zk_036 | 画三角形 ABC，再作三角形 A'B'C' 使其与三角形 ABC 全等（B'C'=BC，A'B'=AB，A'C'=AC） | 平面几何 | ok | ok | ok | solve_fail | ok | llm_refuse | ok | ok | ok |
| zk_038 | 画直角三角形 ABC，∠A=90°，作 BC 的垂直平分线交 AC 于点 D，延长 AC 至点 E，使 CE=AB | 平面几何 | ok | solve_fail | ok | ok | solve_fail | solve_fail | ok | llm_error | llm_error |
| zk_039 | 画⊙O，两条互相垂直的射线 OM、ON，点 P 在⊙O 上，A 在射线 OM 上，B 在射线 ON 上，连接 AP、BP | 平面几何 | ok | ok | solve_fail | llm_refuse | ok | solve_fail | ok | ok | llm_error |
| zk_040 | 在5×7网格中画矩形ABCD，在AB上取点E使AE=2BE，过E画直线EF平分矩形面积；再画△BCD中BD边上的高CG， | 平面几何 | partial | llm_error | ok | llm_refuse | ok | ok | llm_refuse | llm_error | llm_error |
| zk_041 | 画 AC 与 BD 交于点 O，OA=OD，∠ABO=∠DCO，E 为 BC 延长线上一点，过 E 作 EF∥CD 交  | 平面几何 | ok | llm_error | solve_fail | ok | solve_fail | ok | ok | llm_error | llm_error |
| zk_043 | 画三角形 ABD，AC⊥BD 于 C，BC=8，CD=4，BF 为 AD 边上的中线（F 为 AD 中点） | 平面几何 | ok | ok | ok | ok | ok | ok | ok | ok | solve_fail |
| zk_044 | 画四边形 ABCD，∠ACB=90°，∠CAD=∠AEB（AE∥DC），点 E 在 BC 上，过 E 作 EF⊥AB 于 | 平面几何 | ok | ok | llm_refuse | llm_refuse | ok | llm_refuse | ok | llm_refuse | llm_error |
| zk_045 | 画正方形 ABCD 和等腰直角三角形 AEF（∠AFE=90°），H 为 CE 中点，连接 BH、BF、HF，再连接 A | 平面几何 | ok | llm_error | ok | llm_refuse | ok | ok | ok | llm_error | llm_error |
| zk_046 | 补全条形统计图并标注数据 | 统计图表 | refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse |
| zk_047 | 画边长为1的正方形ABCD，E为AD中点，连接BE，将△ABE沿BE翻折得到△FBE，BF交对角线AC于G | 几何变换 | ok | llm_error | ok | ok | ok | ok | ok | ok | ok |
| zk_048 | 在坐标系中画 2 号机的飞行路径：从原点 O 沿 45° 方向上升到 A(4,4)，再水平飞行 1 分钟到 B(7,4) | 坐标系 | ok | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse |
| zk_049 | 画△ABC 和△DEC，∠ACB=∠DCE=90°，BC=AC，EC=DC，点 E 在△ABC 内部，直线 AD 与 B | 平面几何 | ok | solve_fail | solve_fail | ok | ok | ok | ok | ok | llm_error |
| zk_050 | 画三角形 ABC，AD⊥BC 于 D，BD=CD，延长 BC 至 E 使 CE=CA，连接 AE | 平面几何 | ok | solve_fail | ok | ok | ok | solve_fail | solve_fail | ok | llm_error |
| zk_051 | 画四边形 ABCD，CD=80，∠ACD=90°，∠BCD=45°，∠ADC=19°17′，∠BDC=56°19′ | 平面几何 | ok | ok | ok | llm_refuse | ok | ok | ok | ok | ok |
| zk_053 | 画抛物线 y=ax²+c 过点 P(3,0)、Q(1,4)，点 A 在直线 PQ 上，过 A 作 AB⊥x 轴于 B，以 | 函数图像 | refuse | llm_error | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_refuse | llm_error |
| zk_054 | 在平面直角坐标系中画矩形 OABC，C 在 x 轴正半轴，A 在 y 轴正半轴，D 为 AB 的中点，画一次函数 y=- | 坐标系 | partial | llm_error | ok | ok | ok | ok | ok | llm_error | llm_error |
| zk_055 | 画 △ABC 及其外接圆 ⊙O，AD 为 ⊙O 的直径，AD⊥BC 于点 E，连接 BO 并延长交 AC 于点 F，交  | 平面几何 | ok | ok | solve_fail | ok | solve_fail | solve_fail | ok | llm_error | solve_fail |
| zk_056 | 画四边形 ABCD，AB//CD，AB≠CD，∠ABC=90°，点 E、F 分别在 BC、AD 上，EF//CD，AB= | 平面几何 | ok | llm_error | ok | solve_fail | ok | ok | ok | ok | llm_error |
| zk_057 | 画圆 O，半径为 6，将圆周 12 等分，等分点为 A1 到 A12，过 A7 作圆 O 的切线交 A1A11 的延长线 | 平面几何 | ok | llm_error | ok | llm_error | solve_fail | ok | solve_fail | llm_error | llm_error |
| zk_058 | 画以 AB 为直径的半圆，圆心为 O，M、N 在 AB 上，四边形 MNPQ 为内接正方形（P、Q 在半圆上），点 C  | 平面几何 | ok | llm_error | llm_refuse | ok | ok | solve_fail | ok | llm_error | llm_error |
| zk_059 | 已知圆O外一点P，过点P作圆O的一条切线 | 平面几何 | ok | solve_fail | solve_fail | ok | ok | ok | ok | ok | ok |
| zk_060 | 画圆 O 及其内接四边形 ABCD，∠1=∠2（即∠ABD=∠DBC 或对应等角），延长 BC 到点 E 使 CE=AB | 平面几何 | ok | ok | ok | ok | ok | ok | ok | llm_error | ok |
| zk_062 | 画二次函数 y=x²-(m+1)x+m 的图象，与 x 轴交于 A、B 两点，对称轴与 x 轴交于 C，D 在对称轴上第 | 函数图像 | partial | llm_error | llm_refuse | llm_refuse | ok | ok | llm_refuse | llm_error | llm_error |
| zk_063 | 画四边形 ABCD，AB=20，BC=CD=DA=10，AD∥BC，AB 与 CD 交于点 O | 平面几何 | ok | ok | llm_refuse | ok | ok | llm_refuse | ok | ok | llm_refuse |
| zk_064 | 画等腰三角形 ABC，AB=AC，∠BAC=α，M 为 BC 中点，D 在 MC 上，将线段 AD 以 A 为中心顺时针 | 几何变换 | partial | ok | ok | llm_error | ok | solve_fail | ok | solve_fail | llm_error |
| zk_065 | 在圆锥侧面展开图（扇形）中画出从A到母线OC中点B的最短路径线段 | 立体几何 | refuse | ok | llm_refuse | llm_refuse | ok | ok | llm_refuse | ok | llm_refuse |
| zk_066 | 画矩形 ABCD，EF 平行于 AD，GH 平行于 AB，EF 与 GH 交于点 P，在 PF 上取 P1 使 PP1= | 平面几何 | ok | llm_error | solve_fail | llm_refuse | ok | llm_refuse | solve_fail | llm_error | ok |
| gk_001 | 画抛物线 y²=4x 及其焦点 F 和准线，点 A 在抛物线上，过 A 作准线的垂线，垂足为 B，连接 BF | 函数图像 | partial | llm_error | ok | ok | ok | ok | ok | ok | llm_error |
| gk_002 | 画双曲线及其左右焦点 F1、F2，左右顶点 A1、A2，以 F1F2 为直径的圆与一条渐近线交于 M、N 两点 | 平面几何 | refuse | llm_error | llm_refuse | llm_refuse | ok | ok | llm_refuse | llm_error | llm_refuse |

## 表 4 · 定价参考

> 价格为参考估算（元 / 百万 tokens），以各家官网为准。

| Provider | Model 标签 | 输入 (元/M tokens) | 输出 (元/M tokens) |
|---|---|---|---|
| `volcengine` | glm-5.2 (火山 CodingPlan) | 0.5 | 1.5 |
| `deepseek` | deepseek-chat (V4) | 0.5 | 1.5 |
| `minimax` | MiniMax-M3 | 0.5 | 1.5 |
| `volcengine_doubao_pro` | Doubao-Seed-2.0-pro | 0.8 | 2.0 |
| `deepseek_v4_pro` | deepseek-v4-pro (推理模型) | 2.0 | 8.0 |
| `kimi_k26` | kimi-k2.6 | 1.0 | 4.0 |
| `kimi_k27_code` | kimi-k2.7-code | 1.0 | 4.0 |
| `kimi_k27_code_hs` | kimi-k2.7-code-highspeed | 0.5 | 1.5 |

## 表 5 · 综合小结

- **通过率最高**：`volcengine_doubao_pro` — 56/68 ok
- **符合预期最高**：`kimi_k26` — 57/68
- **p50 延迟最低**：`minimax` — p50=9.4s
- **总成本最低**：`volcengine` — ¥0.466
