# 给 AI 助手的工作规约

> 本文件由 OpenCode 在每次对话启动时**自动加载**。下面是这个项目（话图 T2G）的固化工作约定。

## 项目身份

- **名称**：话图 T2G（talk2graph-glm）
- **目标**：用自然语言画 K12 数学几何图形，给老师做课件用
- **MVP 范围**：初中平面几何（三角形、圆、四边形 + 常见约束）
- **不在范围**：函数图像 / 圆锥曲线 / 立体几何 / 统计图表 / 坐标系（V2 计划）

## 开始任何新一轮对话时

按顺序做这 3 件事，**用户不必每次重新说**：

1. **读 `CHANGELOG.md` 顶部块**——拿到当前里程碑、测试数、最近变更、DB schema 状态
2. **读 `docs/onboarding.md`**——拿到行为约束（不要做什么、约定、常见坑）
3. **验证环境健康**：`cd backend && .venv/bin/pytest -q`，与 CHANGELOG 顶部记录的测试数对齐

完成后告诉用户「当前在 W{N}、测试 {n}/{n} 通过」，再等指示。

## 每次完成变更后**必须**做的事

固化为铁律（用户已表达此偏好胜过速度）：

1. ✅ **改代码**
2. ✅ **跑测试**：`cd backend && .venv/bin/pytest -q`；前端有改动则 `npm run build`
3. ✅ **写 CHANGELOG**：在 `CHANGELOG.md` **顶部**加新版本块（新增 / 变更 / 修复 三栏）

漏掉第 3 步会导致下一轮对话无法对齐状态——视为未完成。

## DB Schema 变更专项

如果改了 `app/db/models.py`：

- 开发期：删 `backend/data/talk2graph.db` 让 `init_db()` 重建
- 在 CHANGELOG 该版本块里**明确写出**升级方法
- 影响测试时同步修测试

## 编码约定

- **后端**：Python 3.11、type hints、Pydantic v2、async 优先
- **前端**：TypeScript strict、Zustand store、函数式组件
- **不乱加文件**——优先扩展已有模块
- **不写无用注释**——除非用户明确要求
- **永远不在对话里暴露 API Key / 凭据**

## 关键架构原则（不要随便破坏）

1. **DSL 不含坐标**：LLM 只输出对象 + 约束，坐标由 scipy.least_squares 求解器算
2. **几何精度**：求解残差通常 < 1e-15（机器精度），不允许回退
3. **多 Provider 抽象**：所有 LLM 走 OpenAI 兼容 endpoint；`supports_json_mode` 控制是否传 `response_format`
4. **错误分级**：refuse（黄）/ solve|patch（紫）/ network（红），前端按 `error_kind` 分色
5. **数据持久化**：所有老师 NL、AI 回复、反馈都进 SQLite

## 大改动的工作模式

- 涉及 schema / 路线图变动 / 删文件 → **先 Plan 模式列变更点**，让用户确认再 Build
- 涉及单行 typo 修复、明显 bug → 直接 Build
- 不确定时优先 Plan

## 常见坑（避免重复踩）

| 现象 | 原因 / 处理 |
|---|---|
| 后端报 LLM 网络错误 | uvicorn 没重启；`--reload` 不重读 `.env` → 让用户重启 |
| 火山 LLM 返回 400 `response_format.type` | coding/v3 不支持 json_object → `VolcengineProvider.supports_json_mode=False`（已处理，不要回退）|
| 升级后旧会话打不开 | DB schema 变了 → 开发期删 DB，生产期手动 SQL |
| LLM 拒绝抛物线 | 不是 bug，MVP 不支持圆锥曲线 |
| 测试 `default_provider` 失败 | env 影响；测试只断言在三家之一，别硬编码 |

## 紧急回退

```bash
git status                  # 看动了什么
git diff <file>             # 看具体改动
git checkout -- <file>      # 回退某文件
rm backend/data/talk2graph.db  # DB 回退（开发期）
```

## 主要文件指南

| 文件 | 用途 |
|---|---|
| `README.md` | 项目入口、结构总览 |
| `CHANGELOG.md` | **每次完成变更后必须更新** |
| `docs/onboarding.md` | 详细行为约束 |
| `docs/teacher-guide.md` | 老师使用手册 |
| `frontend/README.md` | 前端开发上手 |
| `deploy/README.md` | 生产部署 |

## 当前 LLM Provider 配置

- 默认：火山方舟 GLM-5.2（`VOLCENGINE_API_KEY` + `VOLCENGINE_ENDPOINT_ID=glm-5.2`）
- 备选：DeepSeek v4-flash（不要用 v4-pro，是推理模型延迟过高）
- 备选：MiniMax-M3
- 备选：智谱直连

完整配置示例在 `backend/.env.example`。
