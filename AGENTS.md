# 给 AI 助手的工作规约（微信小程序版）

> 本文件由 AI 编码工具在每次对话启动时**自动加载**。下面是「话图 T2G 微信小程序版」的固化工作约定。

## 项目身份

- **名称**：话图 T2G 微信小程序版（talk2graph-k3-miniapp）
- **父项目**：talk2graph-glm（Web 版，含完整的 backend + frontend）
- **目标**：把话图 T2G 的 Web 前端（React + Vite）改为微信小程序（原生或 Taro/uniapp），后端 API 完全复用
- **MVP 范围**：初中平面几何 + 立体几何 + 统计图表（与 Web 版 V3.5 对齐）
- **后端不动**：`backend/` 目录是父项目完整代码，API 端点、DB schema、LLM 调用全部复用，**不要改后端**（除非小程序需要新接口，应先在父项目实现再合过来）

## 开始任何新一轮对话时

按顺序做这 3 件事，**用户不必每次重新说**：

1. **读 `CHANGELOG.md` 顶部块**——拿到父项目最新里程碑、测试数、最近变更、DB schema 状态
   - 当前后端是最新版本；小程序端 V1.0（P0+P1：登录/会话/Chat SSE/画板 PNG/导出）已完成
2. **读父项目 `docs/onboarding.md`**——拿到编码约定、常见坑、架构原则
3. **验证后端环境健康**：`cd backend && .venv/bin/pytest -q`，与 CHANGELOG 顶部记录的测试数对齐（当前 353/353）

完成后告诉用户「当前后端在 V3.5、测试 353/353 通过；小程序端 V1.1（登录/会话/Chat SSE/画板 PNG/导出 + 5 家 LLM fallback）已完成」，再等指示。

## 架构原则（从父项目继承，不要破坏）

1. **DSL 不含坐标**：LLM 只输出对象 + 约束，坐标由 scipy.least_squares 求解器算
2. **后端 API 只读**：小程序调 `/api/` 开头的端点，不要改后端路由签名
3. **多 Provider 抽象**：后端 LLM 走 OpenAI 兼容 endpoint；小程序不感知 Provider
4. **错误分级**：refuse（黄）/ solve|patch（紫）/ network（红），小程序按 `error_kind` 分色
5. **数据持久化**：所有老师 NL、AI 回复、反馈都进后端 SQLite；小程序端用微信本地存储做缓存
6. **SSE 流式渲染**：小程序用 `wx.request` + `enableChunked` 接收后端 SSE 流，实时展示对象生成过程

## 小程序 vs Web 的差异（关键）

| 项目 | Web 版 | 小程序版 |
|---|---|---|
| 前端框架 | React + Vite + Zustand | 原生小程序（已定，miniapp/） |
| 路由 | react-router-dom | 小程序 page 注册 |
| 状态管理 | Zustand | 小程序 globalData / mobx-miniprogram / Taro store |
| 样式 | CSS | WXSS（语法兼容 CSS，单位 rpx） |
| Canvas 渲染 | HTML5 Canvas / SVG | Canvas 2D API（同 H5，需适配触控） |
| SSE 流式 | fetch + ReadableStream | `wx.request` + `enableChunked` |
| 导出 | 浏览器 download | `wx.downloadFile` + 保存到相册/分享 |
| 登录 | 邮箱+密码 / 微信扫码 | 微信一键登录 `wx.login` + 后端绑定 |
| 支付 | Alipay 电脑网站支付 | 微信支付 `wx.requestPayment`（需后端加接口） |
| 图片存储 | COS | 微信云存储 / 相册 |

## 编码约定

- **后端**：**不改**（除非确需新接口，优先在父项目实现）
- **小程序端**：
  - 优先扩展已有模块，不乱加文件
  - 保持与 Web 版相同的对象命名（DSL 对象、约束名、API 路径）
  - 不写无用注释
  - **永远不在对话里暴露 API Key / 凭据**

## 父项目设计决策（必须遵循）

- 几何精度 ≠ 0：求解器残差通常 < 1e-15（机器精度），不允许回退
- 立体几何用等轴投影 SVG（不引入 three.js）
- 统计图表走 DSL 对象（不引入 chart.js）
- 邮箱 Provider 抽象：console（开发）/ smtp + 飞书（生产）/ resend（备选）
- 微信 OAuth 代码已就绪（父项目 V3.2 P1），小程序用 `wx.login` 替代 PC 扫码流程
- 配额限流：free 5/天 / pro 30/天 / enterprise 无限
- Admin 后台有批量操作（V3.5）：enable/disable/set_quota/set_subscription

## 小程序改造路线图（建议优先级）

### P0 - 基础架构（1 周）
1. **框架选型**：原生小程序 vs Taro vs uniapp
2. **后端 API client**：封装 `wx.request`，复用 Web 版 `app/client.ts` 的逻辑
3. **微信登录**：`wx.login` + 后端 `/api/auth/wechat/callback` 改造（或用 phoneNumber 绑定）
4. **Canvas 画板**：基础 SVG 渲染（用 `painter` 库或手动封装 Canvas 2D）

### P1 - 核心功能（2 周）
5. **会话管理**：新建/切换/删除/重命名（对照 Web 版 SessionDrawer）
6. **Chat 面板**：输入框 + SSE 流式接收 + 思考气泡 + 错误分类
7. **Canvas 交互**：缩放/平移/点选对象/拖动点（触摸手势）
8. **导出**：保存 Canvas 为图片到相册 + 分享到微信群

### P2 - 用户体系（1 周）
9. **邮箱注册/登录**：对照 Web 版 auth 页面
10. **配额展示**：今日用量 + 剩余 + 套餐信息
11. **付费**：微信支付 `wx.requestPayment`（后端需加微信支付 Provider）
12. **历史会话抽屉**：对照 Web 版 SessionDrawer

### P3 - 增强（2 周）
13. **对象属性面板**：选中对象后显示长度/角度/半径等
14. **提示示例**：首页展示常见图形示例（对照 Web 版 WelcomeCard）
15. **反馈**：👍/👎 按钮 + 评论输入
16. **暗色模式**：跟随系统

## 常见坑（避免重复采）

| 现象 | 原因 / 处理 |
|---|---|
| 后端报 LLM 网络错误 | uvicorn 没重启；`--reload` 不重读 `.env` -> 让用户重启 |
| 火山 LLM 返回 400 `response_format.type` | coding/v3 不支持 json_object -> VolcengineProvider.supports_json_mode=False（已处理） |
| `T2G_FALLBACK_PROVIDERS` 启动报 ValueError | V1.1 起格式为 `provider:model` 逗号分隔（如 `deepseek:deepseek-v4-flash`），纯 provider 名不再合法；可选 6 家：zhipu/volcengine/deepseek/minimax/kimi/bailian |
| `.env` 的 Key 不生效 | shell profile 里 export 了同名变量（如 DEEPSEEK_API_KEY）；`load_dotenv(override=False)` 不覆盖进程 env -> 删掉 shell 里的 export |
| 测试 `default_provider` 失败 | env 影响；测试只断言在三家之一，别硬编码 |
| 改 .env 后不生效 | docker compose up -d backend 重建容器 |
| 配额超限 422 | free 5/天 / pro 30/天；改 DB 立即生效 |
| 微信小程序 Canvas 层级问题 | native-component 不能用 z-index，用 cover-view 覆盖 |
| 小程序 SSE 流式不响应 | `enableChunked: true` + 处理 `data:` 前缀帧 |
| 小程序请求 401 | token 过期，调 `/api/auth/refresh` 续期 |

## 紧急回退

```bash
# 后端（不改就没事，改了出问题用这个）
cd backend && git diff && git checkout -- <file> && rm data/talk2graph.db

# 小程序端
git checkout -- miniapp/    # 回退小程序代码
# 或全局回退
git checkout -- .
```

## 父项目关键文件指南

| 文件 | 用途 |
|---|---|
| `README.md` | Web 版入口、结构总览 |
| `CHANGELOG.md` | **每次完成变更后必须更新** |
| `docs/onboarding.md` | 详细行为约束、架构决策、常见坑 |
| `docs/teacher-guide.md` | 老师使用手册（小程序版可据此改） |
| `docs/email-wechat-setup.md` | 邮件 / 微信 OAuth 配置指南 |
| `backend/app/main.py` | FastAPI 入口、路由注册 |
| `backend/app/api/auth.py` | 登录/注册/微信 OAuth（PC 扫码 + 小程序 wx.login）/邮箱验证 |
| `backend/app/auth/wechat_miniapp.py` | 小程序 jscode2session（code -> openid） |
| `backend/app/api/chat_stream.py` | SSE 流式 chat 端点 |
| `backend/app/dsl/schema.py` | 几何 DSL schema |
| `backend/app/solver/engine.py` | scipy.least_squares 求解器 |
| `backend/app/render/svg.py` | SVG 渲染管线 |
| `backend/.env.example` | 完整配置示例 |
| `miniapp/config.js` | 小程序 API_BASE（dev 127.0.0.1:8000 / 生产 HTTPS 域名） |
| `miniapp/utils/request.js` / `sse.js` | 小程序 API client + SSE 流式（对齐 Web client.ts） |
| `miniapp/utils/api.js` | 小程序动作层（对齐 Web store/index.ts 的 sendChat 流程） |
