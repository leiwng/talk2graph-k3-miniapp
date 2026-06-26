# 话图 T2G · 前端

React 18 + TypeScript + Vite + Zustand。

## 开发

```bash
# 1. 先启后端（另一个终端）
cd ../backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 2. 启前端
cd ../frontend
npm install   # 首次
npm run dev   # 默认 http://localhost:5173
```

Vite 已配置 `/api` 代理到 `http://127.0.0.1:8000`，前端不会有 CORS 问题。

## 不配置任何 LLM Key 时

打开页面后，顶栏所有 Provider 显示为「未配置」，发送对话会得到顶部红色错误条「无法连接 LLM 服务」。
要本地试用，在 `backend/.env` 填入至少一个 Key 后重启后端：

| Provider | 必填 | 默认 base_url |
|---|---|---|
| 火山方舟（GLM-5.2 / 推荐）| `VOLCENGINE_API_KEY` + `VOLCENGINE_ENDPOINT_ID` | `ark.cn-beijing.volces.com/api/coding/v3` |
| DeepSeek | `DEEPSEEK_API_KEY` | `api.deepseek.com` |
| MiniMax | `MINIMAX_API_KEY` | `api.minimaxi.com/v1` |
| 智谱 | `ZHIPU_API_KEY` | `open.bigmodel.cn/api/paas/v4` |

完整配置见 `backend/.env.example`。

## 布局

```
┌──────────────────────────────────────────────────────────┐
│ 话图 T2G  | +新会话 ←撤销 重做→ | seq | Provider▾ 导出▾ │
├──────────────┬───────────────────────────┬───────────────┤
│              │                           │ 对象 (n)      │
│   对话       │       画板 (SVG)          │ ── A 点       │
│   ────────   │                           │ ── B 点       │
│ 你: ...     │   [△ABC + 内切圆]         │ ── ⊙inc      │
│ 话图正在思考│                           │ 约束 (n)      │
│   中…（动画）│                           │ |AB|= [5  ] × │
│ ✓ 图形已更新│  ┌────────────────┐        │ ──────────    │
│             │  │👍 不错  👎 不对│         │ 属性          │
│ [输入框]    │  └────────────────┘        │ ...           │
│ ⌘+Enter 发送│ seq #2  残差 1.2e-8       │               │
└──────────────┴───────────────────────────┴───────────────┘
```

## 已实现

### 核心交互
- 三栏布局（对话 / 画板 / 对象树+属性）
- **输入立即显示**：发送时即时 push 用户气泡 + 「话图正在思考中…」占位（含动画）
- LLM Provider 切换（火山/DeepSeek/MiniMax/智谱），选择写入 localStorage
- 免登录：会话 id 存浏览器 localStorage；服务端 SQLite 持久化

### 错误消息分色（按 `Message.error_kind`）
| 颜色 | error_kind | 含义 |
|---|---|---|
| 🟡 黄色（refuse）| `refuse` | LLM 主动拒绝（题型超出 MVP）|
| 🟣 紫色（solve / patch）| `solve` / `patch` | 求解失败或 patch 应用失败 |
| 🔴 红色（network）| `network` | 网络/鉴权错误，顶部红条 |

### 画板交互
- hover 高亮 + tooltip（点坐标 / 线段长 / 圆半径）
- 拖动点（产生 `hint` 软约束 → 后端重解）
- 右下角 **👍 不错 / 👎 不对** 反馈按钮（点 👎 弹输入框可填原因）
- 切换 seq 自动重置反馈状态

### 其他
- 撤销 / 重做（后端返回 SVG，画板实时同步）
- 属性面板：改约束数值、删约束、改标签、查看坐标
- 导出 SVG / PNG / PDF（PNG/PDF 需后端机器安装 `cairo`）
- 5 个示例对话提示，首次访问可点击直接试

## 关键数据流

```
用户在输入框敲 → 按 ⌘+Enter
       ↓
store.sendChat(nl):
  ① 乐观更新（立刻显示）：
      messages.push({role:"user", content:nl, pending:true})
      messages.push({role:"assistant", content:"__thinking__", pending:true})
  ② busy = true
       ↓
  POST /api/session/{sid}/chat
       ↓ (后端 5-10s)
  ③ 用 api.getMessages(sid) 拉权威列表，替换乐观气泡
  ④ 更新 dsl / solution / svg
  ⑤ busy = false
```

后端返回 `error_kind`：
- `null` → assistant 气泡显示「✓ 图形已更新（N 个对象，M 条约束）」
- `refuse` → 黄色气泡，含产品话术
- `solve` / `patch` → 紫色气泡
- HTTP 502 → 顶部红条 errorBanner

## 状态持久化（localStorage）

| key | 内容 |
|---|---|
| `t2g.current_session_id` | 当前会话 UUID |
| `t2g.provider` | 选中的 Provider 名 |
| `t2g.sessions` | 会话列表缓存 |

## 待办（V2+）

- SSE 流式渲染（替代轮询）
- 历史会话侧抽屉
- 角度/长度直接在画板上点击编辑
- 班级 / 题库管理
- 坐标系支持（V2 范围）
- 函数图像（V2 范围）
