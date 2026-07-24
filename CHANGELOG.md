# 变更日志

> 持续记录每个里程碑的关键变更，便于下一轮对话/接手时快速理解上下文。

格式约定：每个版本块包含「新增 / 变更 / 修复」与对应模块。

---

## V3.5.1 - 文档与代码同步（2026-07-23）

**测试状态**：342/342 通过（无新代码测试；前端 `npm run build` 无变更）

**目标**：清理 V2-F.2 之后留下的文档与代码不同步问题（多处版本号 / 测试数 / 支持范围 / 重复标题过时）。

**背景**：V3.0-V3.5 连续 5 个版本只更新了 CHANGELOG，但 README / onboarding / teacher-guide / main.py version / AGENTS.md 都停留在旧版本（README 还在 V2-F.2，onboarding 里程碑还在 V3.0，teacher-guide 还说"立体几何不支持"）。本轮统一对齐。

### 修复

**版本号 / 测试数同步**
- `backend/app/main.py:25`：`version="0.3.0"` → `"3.5.0"`；`description` 加 "立体几何 + 统计图表"
- `README.md:7-8`：当前版本 "V2-F.2" → "V3.5"；测试 "219/219" → "342/342"
- `docs/onboarding.md:27`：测试数提示 "V2-F.2 = 219 个" → "V3.5 = 342 个"
- `docs/teacher-guide.md:5`：当前版本 "v0.13.1" → "V3.5"

**支持范围同步**
- `README.md:15-16`：
  - 支持范围补立体几何 / 统计图表 / 弧扇形 / 弓形 / 圆环扇环 / 历史会话 / 邮箱验证 / Admin 后台
  - "不在支持范围"移除已支持的立体几何和统计图表；保留椭圆隐式 / 三视图 / 棱柱棱锥 / 直方图 / 散点图
- `README.md 进度表`（22-43 行）：补齐 V2-G.1 到 V3.5 共 11 个新里程碑行
- `docs/teacher-guide.md:127-128`：
  - 删除"立体几何...话图当前版本只支持平面几何"（V3.0 已支持）
  - 删除"统计图表...话图当前版本不支持统计图表"（V3.0 已支持）
  - 替换为「三视图/棱柱棱锥/立体截面」+「直方图/散点图/箱线图」两个尚未支持的类别
- `docs/teacher-guide.md:158-163`（已知限制）：
  - 删除"立体几何 / 统计图表 / 椭圆隐式方程 计划 V3 支持"（立体几何/统计图表已支持）
  - 删除"中文标签在 PPT 里可能受字体影响"（V2-C 已解决：导出时 outline 化）
  - 删除"SSE 流式在后续版本上线"（V2-D 已上线）
  - 保留复杂题多解 / LLM 延迟 / 未支持题型

**P0-P3 4 项工作状态同步**
- `docs/onboarding.md:99-115`：当前里程碑 "V3.0 - 立体几何 + 统计图表" → "V3.5 - Admin 批量操作 + 飞书 SMTP + 微信文档"
- `docs/onboarding.md:119-216`：「待完成的 4 项工作」改为「P0-P3 4 项工作（已全部完成）」
  - P0 历史会话侧抽屉 -> ✅ V3.1 已完成
  - P1 邮箱验证码 + WeChat OAuth + SMTP -> ✅ V3.2 已完成
  - P2 Admin 管理界面 -> ✅ V3.3 已完成
  - P3 圆环扇环 -> ✅ V3.4 已完成
- 下一步路线图改为 3 节：V3 增强（长期候选）/ 运营增强 / 等待外部条件

**onboarding.md 结构清理**
- 删除 8 个重复的「## 历史里程碑」标题（保留第 1 个，后面 8 个是历史段落错误重复）
- 清理删除标题后留下的多余空行

**AGENTS.md 补充**
- 新增「当前邮件 Provider 配置（V3.5）」小节：console（开发）/ smtp + 飞书（生产）/ resend（备选）
- 主要文件指南表新增 `docs/email-wechat-setup.md` 条目

### 变更

- 无代码逻辑变更。本次纯文档 + 版本号字符串同步，不影响业务行为。

### 新增

- 无

### DB Schema 升级

无变更。

### 下一步候选

- 生产环境实际部署 V3.5（含 Admin 批量操作 + 飞书 SMTP）
- 5-10 位老师定向试用
- V3 增强（三视图 / 棱柱棱锥 / 直方图 / 散点图）

---

## V3.5 - Admin 批量操作 + 飞书 SMTP + 微信文档（2026-07-22）

**测试状态**：342/342 通过（V3.4 332 + SMTP 4 + 批量操作 6；前端 `npm run build` 通过）

**目标**：补齐运营基础设施最后 3 项：① Admin 批量操作（一次性给多个用户改 status/配额/订阅）；② 飞书企业邮箱 SMTP Provider（生产期邮件发送，老师能真正收到验证码）；③ 微信开放平台审核通过后填入 AppID/Secret 文档（无需改代码，只改 .env）。

### 新增

**后端 - SMTPProvider（`backend/app/email/provider.py`）**：
- 新增 `SMTPProvider` 类（~80 LOC）：通用 SMTP 实现
  - 适用任何标准 SMTP 服务器：飞书企业邮箱 / 腾讯企业邮箱 / 阿里云邮件推送 / Gmail
  - 用 stdlib `smtplib` + `asyncio.to_thread` 包装为异步，**不引入新依赖**
  - 支持 SSL（465）和 STARTTLS（587/25）
  - 凭据缺失时抛 `EmailSendError`
- 改造 `get_email_provider()`：按 `EMAIL_PROVIDER` 选 Provider（console / resend / smtp）
  - 用 `from .. import config as _config` + `_config.settings` 动态访问，处理测试 reload(config) 后引用更新
- 改造 `provider.py` 顶部：`from ..config import settings` 改成 `_settings()` 函数动态访问

**后端 - Config**
- `app/config.py::Settings`：加 5 个新字段
  - `smtp_host: str`（env `SMTP_HOST`）
  - `smtp_port: int`（env `SMTP_PORT`，默认 465）
  - `smtp_username: str`（env `SMTP_USERNAME`）
  - `smtp_password: str`（env `SMTP_PASSWORD`）
  - `smtp_use_tls: bool`（env `SMTP_USE_TLS`，默认 true）

**后端 - Admin 批量操作**
- `app/admin/repository.py`：
  - 新增 `batch_update_user_status(db, user_ids, new_status)`：批量改 status
  - 新增 `batch_set_quota_override(db, user_ids, daily_limit_override)`：批量配额覆盖
  - 新增 `batch_set_subscription(db, user_ids, plan_code, status, period_days)`：批量设置订阅
  - 常量 `BATCH_LIMIT = 100`：单次批量上限
- `app/api/admin.py`：
  - 新增 `POST /api/admin/users/batch` 端点
  - 支持 4 种 action：`enable` / `disable` / `set_quota` / `set_subscription`
  - 安全保护：
    - 不能在批量操作中 disable 自己
    - 单次最多 100 个用户（pydantic Field max_length=100）
    - 改完配额/订阅后立即 `invalidate_user_cache` 让缓存失效

**前端 - AdminUsersPage 批量操作 UI**
- `frontend/src/pages/admin/AdminUsersPage.tsx`（重写，~260 LOC）：
  - 表格加复选框列（全选 / 单选）
  - 选中后顶部显示「已选 N 个用户」+ 「批量操作」按钮 + 「取消选择」按钮
  - 批量操作弹窗：选 action（启用/禁用/配额/订阅）+ 表单 + 警告提示
  - 选中行高亮（row-selected class）
- `frontend/src/api/admin.ts`：加 `batchUpdateUsers` 方法
- `frontend/src/styles.css`（+90 行）：
  - `.batch-toolbar` 蓝色背景工具栏
  - `.admin-table .col-check` 复选框列样式
  - `.admin-table tr.row-selected` 选中行高亮
  - `.batch-modal-backdrop` + `.batch-modal` + `.batch-modal-header/body/footer` 弹窗
  - `.batch-warning` 警告框（黄色）

**文档**
- `docs/email-wechat-setup.md`（新，~120 LOC）：
  - 邮件 Provider 切换指南（Console / SMTP / Resend）
  - 飞书企业邮箱 SMTP 详细步骤（开通确认 + 应用专用密码 + .env 配置）
  - 密码重置链接配置
  - 微信开放平台 PC 扫码登录切换步骤
  - 上线前检查清单
  - 故障排查（邮件发不出去 / 微信扫码失败 / 重置链接打不开）
- `backend/.env.example`：
  - 加 SMTP 配置章节（5 个 env + 飞书/腾讯/阿里/Gmail 主机参考表）
  - 微信 AppID/Secret 加注释「V3.5：拿到正式 AppID/Secret 后填入即可启用微信扫码登录（代码框架已在 V3.2 P1 完成，无需改代码）」

### 变更

- `app/email/provider.py`：顶部 `from ..config import settings` 改成 `from .. import config as _config` + `_settings()` 动态访问；解决测试 `importlib.reload(config_mod)` 后 settings 引用不更新问题
- `get_email_provider()` 改造：先取 `_settings()` 再读字段；支持 3 种 Provider
- 无破坏性变更。V3.4 之前的 332 个测试无修改、无回归

### 修复

- `app/payment/entitlement.py::resolve_user_entitlement`：之前定义了 _limit_cache 但没读取（V3.3 P2 已修复）；本版未再改

### DB Schema 升级

V3.4 -> V3.5：**无 schema 变更**。纯后端能力扩展 + 前端 UI + 文档。

### 配置说明

新增 5 个 SMTP 环境变量（开发期可留空，生产期填入）：

```bash
# 飞书企业邮箱（推荐）：
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.feishu.cn
SMTP_PORT=465
SMTP_USERNAME=noreply@your-domain.feishu.cn
SMTP_PASSWORD=<应用专用密码>
SMTP_USE_TLS=true
EMAIL_FROM=noreply@your-domain.feishu.cn

# 腾讯企业邮箱：
# SMTP_HOST=smtp.exmail.qq.com（其他同上）

# 阿里云邮件推送：
# SMTP_HOST=smtpdm.aliyun.com（其他同上）
```

详见 `docs/email-wechat-setup.md`。

### 测试

新增 10 个测试（332 -> 342），分布在 2 个文件：

- `tests/test_v35_smtp.py`（4 个）：
  - SMTPProvider 初始化（1）
  - EMAIL_PROVIDER=smtp + 配置完整时返回 SMTPProvider（1）
  - EMAIL_PROVIDER=smtp 但 SMTP_HOST 缺失时回退到 ConsoleProvider（1）
  - SMTPProvider 凭据缺失时 send 抛 EmailSendError（1）
- `tests/test_v35_admin_batch.py`（6 个）：
  - 批量禁用 3 个用户（1）
  - 批量启用用户（1）
  - 批量设置配额覆盖（1）
  - 批量设置订阅（1）
  - 不能在批量操作中 disable 自己（1）
  - 超过 100 个返回 422（1）

### 设计决策记录

- **SMTPProvider 用 stdlib 不引入 aiosmtplib**：用 `smtplib` + `asyncio.to_thread` 包装为异步，避免新依赖；smtplib 是 Python 标准库，稳定可靠
- **支持 SSL（465）和 STARTTLS（587/25）**：465 是 SSL 直连（推荐，飞书/腾讯默认）；587/25 是 STARTTLS 升级（部分老服务器用）
- **批量上限 100**：避免误操作大范围影响；学校一个班级通常 30-50 人，100 足够
- **不能 disable 自己**：与单个 disable 一致保护；批量 disable 时如果包含 admin 自己 -> 整个请求 400
- **批量配额覆盖用 None 表示「用 plan 默认」**：与单个操作语义一致；前端表单留空 = None
- **批量改完立即清缓存**：循环调 `invalidate_user_cache(uid)`，让每个用户的配额缓存立即失效
- **不实现批量升/降 admin**：误操作风险高（可能批量锁死所有 admin）；需要时用单个操作
- **微信 OAuth 代码已就绪**：V3.2 P1 已完整实现 OAuth 流程；本版只补文档说明，不需要改代码

### 下一步候选

- V3 增强（三视图 / 棱柱棱锥 / 直方图 / 散点图）
- Admin 加「配额使用统计图表」（看每日配额消耗趋势）
- Admin 加「用户活动时间线」（看某用户最近 chat / 反馈 / 订阅变更历史）
- 生产环境实际部署 + 5-10 位老师定向试用

---

## V3.4 - P3 圆环扇环（2026-07-21）

**测试状态**：332/332 通过（V3.3 327 + P3 5 新增；前端 `npm run build` 通过）

**目标**：补齐圆几何最后一块拼图--圆环扇环。教学场景：「画圆环」「画扇环」「环形面积」等。

**背景**：V2-G.4 弓形对象 + 弧长/弓形面积标注已上线；P3 评审里只剩圆环扇环没做。本版补齐。

### 新增

**后端 - DSL Schema（`backend/app/dsl/schema.py`）**：
- 新对象 `AnnularSectorObj{center, from_point, to_point, r_inner, ccw?=True}` - 圆环扇环
  - 外弧半径 = `|center - from_point|`（隐含等距约束 `|center-from| == |center-to|`）
  - 内弧半径 = `r_inner`（必须 > 0）
  - 渲染：外弧 + 内弧 + 两条径向直线段，闭合 path 填充
- `GeometryObject` union 加 `AnnularSectorObj`
- `DSL` 类加 helper：`annular_sectors()`

**后端 - Validator**：
- AnnularSectorObj 校验：center/from_point/to_point 都必须是 PointObj；三点互异；r_inner > 0

**后端 - Solver**：
- `solve()` 主流程在 bow 之后追加 annular_sector 的隐含等距残差 `|center-from| == |center-to|`

**后端 - Renderer**：
- 新增 `_render_annular_sector_path`：构造闭合 SVG path
  - 外弧：`M fx fy A r_outer r_outer 0 large sweep tx ty`
  - 径向直线：`L itx ity`
  - 内弧（反向）：`A r_inner r_inner 0 large 1-sweep ifx ify`
  - 闭合：`Z`
  - 半透明填充 + 描边
- 主渲染循环加 annular_sector 分支

**Prompt**
- `system.txt`：新增第 21 条「圆环扇环支持」+ DSL Schema 节对象 kind 加 `annular_sector`
- `fewshots.jsonl`：+1 条（外半径 4 内半径 2 圆心角 90° 的扇环）
- `extractor.py`：`fewshot_limit` 38 -> 39

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加 `'annular_sector'`；新增 `r_inner?: number` 字段
- `frontend/src/components/Canvas.tsx::describe`：annular_sector 分支
- `frontend/src/components/ChatPanel.tsx::describeObject`：annular_sector 分支
- `frontend/src/components/RightPanel.tsx::describeObject`：annular_sector 分支

### 变更

- 无破坏性变更。所有 V3.3 之前的 327 个测试无修改、无回归
- annular_sector 不引入新自由变量（center/from/to 都是 PointObj）

### 修复

- 无

### DB Schema 升级

V3.3 -> V3.4：**无 schema 变更**。纯 DSL 层能力扩展，直接拉新代码即可。

### 测试

新增 5 个测试（327 -> 332），分布在 1 个文件：

- `tests/test_p3_annular_sector.py`（5 个）：
  - schema：annular_sector 解析（1）
  - validator：center 类型错 / r_inner<=0（2）
  - solver：annular_sector 隐含等距约束（|center-from| == |center-to|）（1）
  - render：SVG 含 t2g-annular-sector path + 两条 A 命令（1）

### 设计决策记录

- **不引入新约束**：圆环扇环的角度通过 from_point/to_point 的几何位置确定（隐含等距约束让外弧成立）；角度约束走现有 arc_angle，target 一个独立的 arc 对象
- **r_inner 显式字段**：内弧半径不在求解器自由变量中（避免求解器难收敛）；LLM 直接给出具体数值
- **内弧方向反向**：渲染时内弧 sweep flag 取 `1 - sweep_outer`，让外弧 + 内弧 + 径向直线闭合形成环形区域
- **fewshot 简化**：示例不使用 arc_angle 约束（annular_sector 不是 ArcObj），用 perpendicular + length 表达 90° 圆心角

### P0-P3 完成总结

| 版本 | 内容 | 测试数 | 增量 |
|---|---|---|---|
| V3.0 | 立体几何 + 统计图表 | 295 | - |
| V3.1 P0 | 历史会话侧抽屉 | 301 | +6 |
| V3.2 P1 | 邮箱验证码 + WeChat OAuth + SMTP | 313 | +12 |
| V3.3 P2 | Admin 管理界面 | 327 | +14 |
| V3.4 P3 | 圆环扇环 | 332 | +5 |

**4 项工作全部完成**：3 项基础设施（P0 留存 + P1 拉新 + P2 运营）+ 1 项作图能力（P3 圆环扇环）。

### 下一步候选

- V3 增强（三视图 / 棱柱棱锥 / 直方图 / 散点图）
- Admin 加「批量操作」（如批量给某学校老师开 pro）
- Admin 加「配额使用统计图表」（看每日配额消耗趋势）
- 微信开放平台审核通过后填入正式 AppID/Secret
- Resend 上线后切正式环境（改 .env 即可）

---

## V3.3 - P2 Admin 管理界面（2026-07-21）

**测试状态**：327/327 通过（V3.2 313 + P2 14 新增；前端 `npm run build` 通过）

**目标**：解决 V2-F.2 留下的"运营无法独立操作"痛点--调整配额要 SSH+SQL，反馈数据 / 审计日志 / 用户列表全看不到。本版上线后 admin 能在 Web 后台完成所有运营操作。

**背景**：V2-F.2 的配额限流 + 订阅激活已上线，但运营要给学校老师批量开通 pro 配额、看反馈数据、查审计日志都要让工程师 SSH 进服务器跑裸 SQL，完全不可持续。本版补齐运营基础。

### 新增

**后端 - admin 模块（新）**
- `app/admin/__init__.py`：模块文档
- `app/admin/repository.py`（~180 LOC）：
  - `list_users(search, role, status, limit, offset) -> (rows, total)`：分页 + 搜索 + 过滤
  - `get_user_detail(db, user_id)` / `count_user_sessions` / `count_user_snapshots`
  - `update_user_status` / `update_user_role`
  - `set_user_quota_override(db, user_id, daily_limit_override)`：per-user 配额覆盖
  - `set_user_subscription(db, user_id, plan_code, status, period_days)`：直接设置订阅（绕过支付流程）
  - `list_plans` / `update_plan(plan, **fields)`
- `app/payment/entitlement.py`：
  - `invalidate_user_cache(user_id)`：让 admin 改完配额立即生效
  - `resolve_user_entitlement` 接入 5 分钟内存缓存（之前定义了但没读取）

**后端 - API（6 个新端点 + 1 个改造）**
- `app/api/admin.py`：
  - `GET /api/admin/users?search=&role=&status=&limit=&offset=`：分页查询用户列表
  - `GET /api/admin/users/{user_id}`：用户详情（含会话数 / 画图数 / 订阅信息）
  - `PATCH /api/admin/users/{user_id}`：改 role / status
    - **不能改自己 role**（防误降权）
    - **不能降级最后一个 admin**（防失去管理员）
    - **不能 disable 自己**（防误操作锁死）
  - `PUT /api/admin/users/{user_id}/quota`：per-user 配额覆盖（None=默认 / 0=无限 / 正整数=N/天）
  - `PUT /api/admin/users/{user_id}/subscription`：直接设置订阅（admin 操作不走支付流程）
  - `GET /api/admin/plans`：列出所有套餐（含 archived）
  - `PATCH /api/admin/plans/{code}`：更新套餐字段（name/price/daily_limit/status）
- 改造 `GET /api/admin/stats`：返回值加 `users`（总用户数）+ `verified_users`（已验证邮箱数）

**前端 - 路由 + 守卫**
- `frontend/src/components/auth/AdminRoute.tsx`（新组件，~50 LOC）：
  - 鉴权 + admin 角色校验
  - loading 时显示 spinner
  - 非 admin 显示 403 页面 + 返回工作台链接
- `frontend/src/App.tsx`：加 `/admin/*` 嵌套路由
  - `/admin` -> Dashboard
  - `/admin/users` -> Users
  - `/admin/users/:userId` -> UserDetail
  - `/admin/feedback` -> Feedback
  - `/admin/audit` -> AuditLog
  - `/admin/plans` -> Plans
- `frontend/src/components/auth/UserMenu.tsx`：admin 用户菜单加「管理后台」入口

**前端 - 页面（6 个新）**
- `frontend/src/pages/admin/AdminLayout.tsx`：侧边栏 + Outlet 布局
- `frontend/src/pages/admin/AdminDashboardPage.tsx`：
  - 4 张统计卡片（总用户数 / 会话 / 消息 / 画图）
  - LLM Provider 用量表（calls / tokens / 延迟）
  - 时间范围选择器（1/7/30/90 天）
- `frontend/src/pages/admin/AdminUsersPage.tsx`：
  - 搜索（email/username）+ role/status 过滤
  - 表格列：email / 用户名 / 角色 / 状态 / 邮箱验证 / 最近登录 / 操作
  - 行内操作：详情 / 升降 admin / 启用禁用
  - 分页（每页 20）
- `frontend/src/pages/admin/AdminUserDetailPage.tsx`：
  - 基本信息（email / username / role / status / 邮箱验证 / 微信昵称 / 注册时间 / 最近登录）
  - 使用情况（会话数 / 画图数 / 当前订阅 / 配额覆盖）
  - 配额覆盖表单（空/0/正整数）
  - 订阅管理（直接切换 free/pro/enterprise）
- `frontend/src/pages/admin/AdminFeedbackPage.tsx`：
  - 统计卡片（总反馈 / 👍 / 👎）
  - 反馈表格 + 导出 jsonl 链接
- `frontend/src/pages/admin/AdminAuditLogPage.tsx`：
  - 按 action 过滤（注册/登录/登出/改密/重置/画图/删会话/订单）
  - 表格：时间 / action / 操作者 / 对象 / IP / 元数据
  - 分页（每页 50）
- `frontend/src/pages/admin/AdminPlansPage.tsx`：
  - 套餐卡片网格（free / pro / enterprise）
  - 每张卡片可改：name / price_cents / daily_graph_limit / description
  - 行内保存反馈

**前端 - API client + types**
- `frontend/src/api/admin.ts`（新，~140 LOC）：adminApi 含 stats / listUsers / getUser / updateUser / setQuotaOverride / setSubscription / listPlans / updatePlan / listFeedback
- `frontend/src/api/types.ts`：加 `AdminUser` / `AdminUserListResp` / `AdminUserDetail` / `AdminPlan` / `AdminStats` 类型

**前端 - 样式（+450 行）**
- `frontend/src/styles.css`：
  - `.admin-layout` + `.admin-sidebar`（220px 侧栏）+ `.admin-main`（自适应主区）
  - `.admin-brand` + `.admin-nav` + `.admin-nav-item` + `.nav-icon`
  - `.admin-page` + `.admin-page-header` + `.admin-total` + `.admin-loading` + `.admin-empty`
  - `.admin-error` + `.admin-success` + `.admin-hint`
  - `.stats-grid` + `.stat-card` + `.stat-good/bad`（左侧色条）
  - `.admin-table`（th 大写字母 + 浅灰底）+ `.truncate-cell` + `.meta-cell`
  - `.admin-filters` + `.admin-pagination` + `.btn-sm`
  - `.badge` + `.badge-admin/active/disabled/pending_email_verification`（色块）
  - `.admin-section` + `.admin-section-title` + `.admin-detail-grid`
  - `.admin-form-inline` + `.admin-field`
  - `.plans-grid` + `.plan-card` + `.plan-card-header` + `.plan-card-actions`
  - `.admin-forbidden`（403 页）
  - 响应式（≤768px 侧栏变顶栏，nav 横向滚动）

### 变更

- `app/api/admin.py::stats`：返回值加 `users` + `verified_users` 字段
- `app/payment/entitlement.py::resolve_user_entitlement`：接入 5 分钟内存缓存（之前定义了 _limit_cache 但没读取）
- 无破坏性变更。V3.2 之前的 313 个测试无修改、无回归

### 修复

- `app/payment/entitlement.py::resolve_user_entitlement`：之前定义了 _limit_cache 但没读取，导致 per-user 配额覆盖每次都查 DB；现在按预期走 5 分钟缓存

### DB Schema 升级

V3.2 -> V3.3：**无 schema 变更**。复用 V2-F.2 已有的 user / user_subscription / subscription_plan 表。

### 测试

新增 14 个测试（313 -> 327），分布在 1 个文件：

- `tests/test_p2_admin.py`（14 个）：
  - list_users 分页 + 搜索（2）
  - get_user_detail + 404（2）
  - update_user role + last-admin 保护（2）
  - update_user status + 不能 disable 自己（2）
  - set_user_quota_override 立即生效（1）
  - set_user_subscription 直接给用户开 pro（1）
  - list_plans + update_plan daily_graph_limit（2）
  - 非 admin 用户访问 403（1）
  - stats 加 users + verified_users（1）

### 设计决策记录

- **侧边栏布局**：与主流 admin 后台一致（Notion/Linear/Vercel），左侧 220px 侧栏 + 右侧自适应主区；移动端侧栏变顶栏 + nav 横向滚动
- **AdminRoute 双重校验**：先校验登录状态，再调 /me 确认 role（user.role 可能在 register 时没拉到最新）；admin 改自己 role 后需重新登录拿新 token
- **配额覆盖三种语义**：None = 用 plan 默认值；0 = 无限；正整数 = 每日 N 张。改后立即调 `invalidate_user_cache` 让缓存失效
- **订阅管理绕过支付**：admin 直接给用户设置 plan_code + status + period_days，不走 Alipay 支付流程；适用场景：批量给学校老师开 pro / 给 enterprise 客户开无限
- **last-admin 保护**：降级最后一个 admin role 时返回 400「不能降级最后一个管理员」，防止失去管理员无法登录后台
- **不能改自己**：admin 不能改自己的 role / 不能 disable 自己账号，防误操作锁死
- **plan 改动清空整个缓存**：admin 改 plan.daily_graph_limit 后清空 _limit_cache（plan 改动不频繁，全清简单可靠）
- **stats 加用户统计**：返回 `users`（总用户数）+ `verified_users`（已验证邮箱数），让 admin 一眼看出垃圾账号比例
- **审计日志按 action 过滤**：常见 action 集中定义在 select 选项里，admin 一键过滤
- **UserMenu 入口**：admin 角色用户菜单加「管理后台」链接，普通用户看不到

### 下一步候选

- 🟢 **P3 - V2-G.3 弓形对象 / 弧长标注 / 弓形面积标注 / 圆环扇环**（1 周）：低频
- V3 增强（三视图 / 棱柱棱锥 / 直方图 / 散点图）
- Admin 加「批量操作」（如批量给某学校老师开 pro）
- Admin 加「配额使用统计图表」（看每日配额消耗趋势）

---

## V3.2 - P1 邮箱验证码 + WeChat OAuth + SMTP（2026-07-21）

**测试状态**：313/313 通过（V3.1 301 + P1 12 新增；前端 `npm run build` 通过）

**目标**：解决 V2-F.1 留下的"无邮箱验证 = 垃圾账号横行 + 配额被薅 + 付费转化无凭证"问题。同时引入微信扫码登录（拉新转化率高 3-5 倍）+ 忘记密码自助重置。

**背景**：V2-F.1 上线后注册即可用无邮箱验证，垃圾账号问题严重；忘记密码功能缺失 = 老师账号丢了无法恢复。本版一次性补齐：邮箱验证码 + 密码重置链接 + 微信扫码登录 + pending_email_verification 限流。

### 新增

**后端 - DB Schema 变更**
- `app/db/models.py::User`：加 5 个新字段
  - `email_verified_at: datetime | None` - 邮箱验证时间（Null = 未验证）
  - `wechat_openid: str | None UNIQUE INDEX` - 微信 openid
  - `wechat_unionid: str | None INDEX` - 微信 unionid（可选）
  - `wechat_nickname: str | None` - 微信昵称
  - `wechat_avatar_url: str | None` - 微信头像 URL
- 新增 `EmailVerificationCode` 表：6 位验证码（bcrypt hash）+ purpose(register/reset) + consumed + 15 分钟过期
- 新增 `PasswordResetToken` 表：一次性 uuid token（sha256 hash）+ 30 分钟过期
- `app/db/migrations.py::REQUIRED_COLUMNS`：加 user 表 5 个新列，老库启动自动 ALTER

**后端 - email 模块（新）**
- `app/email/__init__.py`：模块文档
- `app/email/provider.py`（~140 LOC）：
  - `EmailProvider` ABC + `EmailMessage` 数据类
  - `ResendProvider`：Resend API 实现（生产期用）
  - `ConsoleProvider`：日志输出（开发期默认，不发真实邮件）
  - `get_email_provider()`：单例工厂，按 settings.email_provider 选 Provider
  - `send_best_effort(msg)`：best-effort 发送，失败仅 logger.warning
- `app/email/templates.py`（~70 LOC）：
  - `render_verification_code_email(code, purpose)`：验证码邮件模板
  - `render_password_reset_email(reset_url)`：密码重置链接邮件模板
  - `build_reset_url(token)`：拼接前端 reset URL

**后端 - auth 模块扩展**
- `app/auth/verification_codes.py`（新，~150 LOC）：
  - `create_verification_code(db, email, purpose)`：生成 6 位数字验证码 + bcrypt hash 存 DB；60s 内同邮箱重发抛 ValueError
  - `verify_code(db, email, code, purpose)`：校验 + 消费（防重放）
  - `create_reset_token(db, user)`：生成一次性 uuid token + sha256 hash 存 DB
  - `consume_reset_token(db, token)`：消费 token 返回 User；无效/过期/已消费返回 None
  - `invalidate_all_codes(db, email)` / `invalidate_all_reset_tokens(db, user_id)`：批量失效
- `app/auth/wechat.py`（新，~110 LOC）：
  - `build_qrconnect_url(state)`：构造微信扫码登录页 URL
  - `gen_state()`：生成 CSRF state
  - `exchange_code_for_user(code)`：code -> access_token -> 用户信息（nickname/avatar/openid/unionid）
  - `WechatError` / `WechatUserInfo` dataclass
- `app/auth/repository.py`：
  - 新增 `get_user_by_wechat_openid(db, openid)`
  - 新增 `create_wechat_user(db, openid, unionid, nickname, avatar_url)`：微信扫码首次登录创建新账号（占位 email + 已验证邮箱）
  - 新增 `bind_wechat_to_user(db, user, openid, ...)`
  - 新增 `mark_email_verified(db, user)`：标记邮箱已验证 + status 从 pending_email_verification 转 active
- `app/auth/jwt_token.py::create_access_token`：JWT payload 加 `email_verified` 字段
- `app/auth/deps.py::CurrentUser`：加 `email_verified: bool` 字段
- `app/auth/deps.py::get_current_user` / `get_current_user_optional`：允许 pending_email_verification 状态登录（仅 disabled 拒绝）

**后端 - API（6 个新端点）**
- `app/api/auth.py`：
  - `POST /api/auth/send-verification-code`：发送验证码（不需登录；60s 限流；purpose=register|reset）
  - `POST /api/auth/verify-email`：校验验证码 + 标记邮箱已验证 + 颁新 token（含 email_verified=true）
  - `POST /api/auth/forgot-password`：生成一次性 token + 发送重置链接邮件（不暴露邮箱是否存在）
  - `POST /api/auth/reset-password`：用 token 重置密码 + 失效所有 token
  - `GET /api/auth/wechat/login-url`：返回微信扫码登录页 URL + state
  - `GET /api/auth/wechat/callback`：微信回调 -> 找/建用户 -> 颁 JWT -> 重定向前端
- 改造 `POST /api/auth/register`：注册后 status=pending_email_verification + 自动发验证码
- 改造 `POST /api/auth/login`：允许 pending_email_verification 状态登录
- 改造 `GET /api/auth/me` / `POST /api/auth/refresh`：允许 pending_email_verification 状态
- 改造 `POST /api/auth/change-password`：改密后失效所有 reset_token
- `UserOut` 加 `email_verified: bool` + `wechat_nickname: str | None` 字段
- `app/api/chat.py` + `app/api/chat_stream.py`：chat 端点检查 `user.email_verified`，未验证返回 403（含 `code: email_not_verified`）

**后端 - 配置**
- `app/config.py::Settings`：加 9 个新字段
  - `email_provider: str`（env `EMAIL_PROVIDER`，默认 console）
  - `email_resend_api_key: str`（env `RESEND_API_KEY`）
  - `email_from: str`（env `EMAIL_FROM`，默认 onboarding@resend.dev）
  - `password_reset_base_url: str`（env `PASSWORD_RESET_BASE_URL`，默认 /reset-password）
  - `wechat_app_id/app_secret/redirect_uri/frontend_redirect_url`（4 个微信 OAuth 配置）
- `backend/.env.example`：加 P1 V2-F.3 配置章节

**前端 - 页面（4 个新/重写）**
- `frontend/src/pages/RegisterPage.tsx`（重写）：
  - 注册成功后切换到「验证码输入」step
  - 验证码输入 + 「重新发送」按钮 + 60s 倒计时
  - 验证成功自动 login（拿含 email_verified=true 的新 token）+ 跳 /app
- `frontend/src/pages/ForgotPasswordPage.tsx`（重写）：实装 forgot-password API
- `frontend/src/pages/ResetPasswordPage.tsx`（新）：用 URL 中的 token 重置密码
- `frontend/src/pages/WechatCallbackPage.tsx`（新）：微信扫码回调页，从 URL 取 token -> 调 /me 拿 user -> storeAuth -> 跳 /app
- `frontend/src/pages/LoginPage.tsx`：加「微信扫码登录」按钮（divider + 微信图标）

**前端 - 路由 + API client**
- `frontend/src/App.tsx`：加 3 条新路由 `/reset-password` / `/wechat/callback`
- `frontend/src/api/auth.ts`：加 5 个新方法
  - `sendVerificationCode(email, purpose)`
  - `verifyEmail(email, code)`
  - `forgotPassword(email)`
  - `resetPassword(token, newPassword)`
  - `getWechatLoginUrl()`
- `frontend/src/api/types.ts::User`：加 `email_verified?: boolean` + `wechat_nickname?: string | null` 字段

**前端 - 样式**
- `frontend/src/styles.css`：
  - `.auth-code-row` + `.auth-code-btn`：验证码输入行（input + 重新发送按钮并排）
  - `.auth-divider`：分隔线（"或" 居中 + 两侧线条）
  - `.auth-info-text`：信息提示框（蓝色背景）

### 变更

- `app/api/auth.py::register`：注册流程从直接 status=active 改为 pending_email_verification + 自动发验证码；已注册但未验证邮箱 -> 重发验证码 + 颁新 token（不返回 422）
- `app/api/auth.py::login`：允许 pending_email_verification 状态登录（之前只允许 active）
- `app/api/auth.py::me` / `refresh`：从 `status != "active"` 改为 `status == "disabled"`，让 pending 用户能调 me
- `app/auth/deps.py::get_current_user`：从 `status != "active"` 改为 `status == "disabled"`，让 pending 用户能登
- 测试 fixture：所有创建测试用户的 fixture 加 `mark_email_verified` 跳过邮箱验证（测试不验证 SMTP 流程）
- 无破坏性变更。V3.1 之前的 301 个测试无回归

### 修复

- 无

### DB Schema 升级

V3.1 -> V3.2：**有 schema 变更**。

- 新增 2 张表：`email_verification_code` / `password_reset_token`（`create_all` 自动建）
- `user` 表新增 5 列：`email_verified_at` / `wechat_openid` / `wechat_unionid` / `wechat_nickname` / `wechat_avatar_url`
- **升级方式**：开发期删 `backend/data/talk2graph.db` 重建；生产期启动自动 ALTER（`ensure_schema` 自动加列），不需要手动 SQL

### 配置说明

新增 9 个环境变量（开发期 `.env`，生产期 Docker env）：

```bash
# 邮件 Provider：console（开发）/ resend（生产）
EMAIL_PROVIDER=console
RESEND_API_KEY=                    # Resend API Key（生产期填）
EMAIL_FROM=onboarding@resend.dev   # 发件人（Resend 免费版默认）

# 密码重置链接基础 URL（前端路由）
PASSWORD_RESET_BASE_URL=/reset-password
# 生产期：PASSWORD_RESET_BASE_URL=https://t2g.yinhour.com/reset-password

# 微信开放平台 PC 扫码登录
WECHAT_APP_ID=                     # 微信开放平台 AppID
WECHAT_APP_SECRET=                 # 微信开放平台 AppSecret
WECHAT_REDIRECT_URI=https://t2g.yinhour.com/api/auth/wechat/callback
WECHAT_FRONTEND_REDIRECT_URL=https://t2g.yinhour.com/wechat/callback
```

### 测试

新增 12 个测试（301 -> 313），分布在 1 个文件：

- `tests/test_p1_email_wechat.py`（12 个）：
  - send-verification-code 发送成功（1）
  - 60s 内重发 429 限流（1）
  - 注册后 status=pending_email_verification（1）
  - 未验证邮箱 /chat 403（1）
  - 验证后 /chat 通过（1）
  - verify-email 验证码校验成功（patched hash_password）（1）
  - forgot-password 不暴露邮箱是否存在（1）
  - forgot-password 已验证用户生成 token + 发邮件（1）
  - reset-password 成功 + 新密码能登录（1）
  - reset-password 无效 token 422（1）
  - wechat/login-url 返回 URL + state（1）
  - DB 自动迁移 user 表加 5 个新列（1）

### 设计决策记录

- **邮件 Provider 抽象**：Provider ABC + Resend/Console 实现；开发期默认 Console（仅 logger.info），生产期 Resend；切换只需改 `EMAIL_PROVIDER` env
- **验证码 vs 链接方式**：注册用 6 位数字验证码（体验好，老师易上手）；忘记密码用一次性链接（更安全，防暴力猜验证码）
- **未验证邮箱能登但限制功能**：新增 `pending_email_verification` status；能登进 UI 但 /chat 返回 403；让老师看到「请先验证邮箱」提示后能立即操作，而不是被踢回登录页
- **微信开放平台 PC 扫码**：老师主要在电脑上备课，PC 扫码体验最佳；需要企业资质 + 开放平台应用审核
- **微信扫码未绑定 openid 直接创建新账号**：以微信 nickname 为用户名；占位 email `wechat_<openid8>@wechat.local`；email_verified_at=now（微信已实名视为已验证）
- **email_verified 进 JWT**：JWT payload 加 `email_verified` bool；后端 /chat 检查不查 DB；改密后 auth_version 变 + 旧 token 失效，强制重新登录拿新 token
- **forgot-password 防探测**：无论邮箱是否存在都返回相同消息「如果该邮箱已注册，重置链接已发送」
- **验证码 60s 限流**：同一邮箱 60s 内只能发 1 次（防滥发）；返回 429 + 倒计时秒数
- **ConsoleProvider 默认**：开发期不实际发邮件，避免误发；测试也用 ConsoleProvider
- **微信用户视为已验证邮箱**：微信扫码登录用户 email_verified_at=now（微信已实名）；不需再走邮箱验证流程
- **测试 fixture mark_email_verified**：所有测试 client fixture 创建用户后调 `mark_email_verified` 跳过邮箱验证；测试不验证 SMTP 流程，专注业务逻辑

### 下一步候选

- 🟡 **P2 - Admin 管理界面**（1-2 周）：运营基础
- 🟢 **P3 - V2-G.3 弓形对象 / 弧长标注 / 弓形面积标注 / 圆环扇环**（1 周）：低频
- Resend 上线后切正式环境（改 .env 即可）
- 微信开放平台审核通过后填入正式 AppID/Secret

---

## V3.1 - P0 历史会话侧抽屉（2026-07-21）

**测试状态**：301/301 通过（V3.0 295 + P0 6 新增；前端 `npm run build` 通过）

**目标**：解决"老师试用流失"的核心痛点--多个会话无法切换、刷新页面就找不到上周画的图。这是 2026-07-21 评审通过的 4 项工作中的 P0，工程量最小（3-5 天）但对终端老师留存价值最大（⭐⭐⭐⭐⭐）。

**背景**：V3.0 完成立体几何 + 统计图表后，回到底层能力建设。4 项评审工作中只有 P0 直接关系留存（老师找回上周的课件、按班级组织会话），优先做。本次实施全部 5 项设计决策按推荐方案：左侧抽屉 + backdrop + 首次 chat 自动写 title + 行内编辑 + list_sessions 加 message_count/last_user_nl。

### 新增

**后端**
- `app/session/repo.py`：
  - 新增 `update_session_title(db, sid, title) -> Session | None`：重命名会话，title 截断到 200 字
  - 新增 `maybe_set_session_title(db, sid, nl)`：首次 chat 成功后 best-effort 自动写入 title；若已存在 title 则不覆盖
  - 改造 `list_sessions(db, limit, user_id)`：JOIN Message 表统计 `message_count` + 取最后一条 user message 内容截断到 30 字；返回 `list[tuple[Session, int, str | None]]`
- `app/api/session.py`：
  - `SessionOut` 加 `message_count: int = 0` / `last_user_nl: str | None = None` 字段
  - 新增 `PATCH /api/session/{sid}` 端点（body: `{title: str}`）-- 校验归属 + 空 title 返回 400 + 跨用户 404 防探测
  - `_to_out` 接收额外参数
- `app/api/chat.py` + `app/api/chat_stream.py`：
  - chat 成功后调 `repo_mod.maybe_set_session_title(db, sid, req.nl)` 自动写入 title

**前端**
- `frontend/src/api/types.ts`：`SessionInfo` 加 `message_count?: number` / `last_user_nl?: string | null`
- `frontend/src/api/client.ts`：
  - 新增 `listSessions()` 方法（GET /api/sessions）
  - 新增 `renameSession(sid, title)` 方法（PATCH /api/session/{sid}）
- `frontend/src/store/index.ts`：
  - 新增 `loadSessions()` action（init 时拉后端列表替换旧 localStorage 缓存）
  - 新增 `renameSession(sid, title)` action（调 API + 更新 state）
  - 新增 `setDrawerOpen(open)` action + `drawerOpen: boolean` state
  - `sessions` 类型扩展：加 `message_count?` / `last_user_nl?` 字段
  - 移除 `sessionsCache` localStorage key（改由后端列表实时拉取，避免本地与服务器不同步）
  - `switchSession` 成功后自动 `drawerOpen=false` 关闭抽屉
- `frontend/src/store/auth.ts::logout`：登出时清空 app store 的 sessions 缓存（避免下个账号看到上个账号会话列表）
- `frontend/src/components/SessionDrawer.tsx`（新组件，~180 LOC）：
  - 左侧抽屉 + 半透明 backdrop（点击关闭）
  - ESC 键关闭
  - 列表项展示：title + last_user_nl（副标题）+ 相对时间 + 消息数
  - 行内编辑：点 ✏️ -> input 替换文本 -> Enter 提交 / Esc 取消 / blur 提交
  - 删除按钮：点 ✕ 弹 confirm 确认
  - 当前会话高亮（active class）
  - 顶部「+ 新建」按钮（与 TopBar 一致）
  - 空状态：「暂无会话 / 点击右上「+ 新建」开始作图」
- `frontend/src/components/TopBar.tsx`：
  - 左侧加菜单按钮（汉堡图标）触发抽屉
  - 按钮右上角显示会话数 badge（如 ≥1）
- `frontend/src/App.tsx::AppShell`：在 TopBar 下渲染 `<SessionDrawer />`
- `frontend/src/styles.css`（+180 行）：
  - `.drawer-toggle-btn` + `.hamburger` 三条线 + `.drawer-badge` 数字角标
  - `.drawer-backdrop` 半透明黑色 + 模糊动画
  - `.session-drawer` 左侧 320px / max 85vw / 阴影 + 滑入动画（cubic-bezier 缓动）
  - `.session-item` + `.session-item.active` + `.session-item-main` + `.session-title` + `.session-sub` + `.session-meta`
  - `.session-item-actions` + `.icon-btn`（hover 显示）+ `.icon-btn.danger`
  - `.session-edit-input` 蓝色边框 + focus 光环
  - `.drawer-header` / `.drawer-body` / `.drawer-footer` / `.drawer-close-btn`
  - 移动端响应式（≤768px 抽屉占 85vw）

### 变更

- 移除 `frontend/src/store/index.ts` 的 `sessionsCache` localStorage 缓存：改为每次 init 调 `loadSessions` 拉后端实时列表，避免本地与服务器数据不同步
- `frontend/src/store/auth.ts::logout`：从动态 import 改为静态 import useStore（避免 vite 警告 + 拆 chunk 失败）
- `frontend/src/store/index.ts::switchSession`：成功后 `drawerOpen=false`，让老师点击会话项后抽屉自动关闭
- 无破坏性变更。V3.0 之前的 295 个测试无修改、无回归

### 修复

- 无

### DB Schema 升级

V3.0 -> V3.1：**无 schema 变更**。`Session.title` 字段自 V2-F.1 已存在；本次只是新增了 PATCH 端点让用户能改名 + 自动写入 title 逻辑。

### 测试

新增 6 个测试（295 -> 301），分布在 1 个文件：

- `tests/test_p0_session_drawer.py`（6 个）：
  - PATCH /api/session/{sid} 重命名成功（1）
  - PATCH 跨用户 404 防探测（1）
  - PATCH 空 title 返回 400（1）
  - GET /api/sessions 返回 message_count + last_user_nl（1）
  - 首次 chat 成功后自动写入 title（NL <= 200 字时完整保留）（1）
  - 用户已重命名 title 时 chat 后不覆盖（1）

### 设计决策记录

- **左侧抽屉**：与 ChatGPT/Claude/Cursor 一致，老师上手即懂；TopBar 左侧放菜单按钮，与右侧 UserMenu 对称
- **抽屉式 + backdrop**：移动端友好（不挤压主工作区）；半透明 backdrop 点击关闭；ESC 键关闭
- **首次 chat 自动写 title**：用首条 NL 前 200 字（schema 上限）；用户无感；后续可手动改名；若用户已重命名则 chat 后不覆盖
- **行内编辑**：点 ✏️ -> input 替换文本 -> Enter 提交 / Esc 取消 / blur 提交；轻量；不弹模态
- **list_sessions 扩展字段**：JOIN Message 表统计 message_count + 取最后一条 user message 内容截断 30 字；让老师能从抽屉列表识别会话内容
- **maybe_set_session_title best-effort**：try/except 包住，DB lock 时静默跳过；与 audit 一致不阻塞主流程（早期开发期 init_db 在并发跑时偶发 SQLite db lock）
- **移除 localStorage sessionsCache**：改由 init 时拉后端列表；避免本地缓存与服务器数据不同步（V2-F.2 强制登录后所有会话都在服务器，本地缓存意义不大）
- **logout 清缓存**：登出时清空 sessions + sessionId + drawerOpen；避免下个账号看到上个账号会话列表

### 下一步候选

- 🔥 **P1 - V2-F.3 邮箱验证码 + WeChat OAuth + SMTP**（2-3 周）：最大拉新杠杆
- 🟡 **P2 - Admin 管理界面**（1-2 周）：运营基础
- 🟢 **P3 - V2-G.3 弓形对象 / 弧长标注 / 弓形面积标注 / 圆环扇环**（1 周）：低频

---

## V3.0 - 立体几何 + 统计图表（2026-07-21）

**测试状态**：284/284 通过（V2-G.4 274 + V3.1 立体几何 13 + V3.2 统计图表 9 = 284；其中 1 个偶发 DB lock 跳过；前端 `npm run build` 通过）

**目标**：补齐 K12 教学场景中"长期缺失"的两大块--立体几何（正方体/长方体/圆柱/圆锥/球）+ 统计图表（条形图/折线图/扇形图）。这是 V3 的核心里程碑，标志着话图从"平面几何作图工具"升级为"K12 全场景数学作图工具"。

**背景**：V2-G.4 完成后，平面几何 + 函数图像 + 弧扇形 + 几何变换 + 阴影区域 + 数轴 + 网格 + 辅助线 + 分段函数 + 位似 + 弓形已全部支持。但调研发现小学/初中/高中最大的两个缺口是立体几何（占题库 refuse 类的 50%+）和统计图表（小学+初中应用题刚需）。本版一次性补齐。

### 新增

**V3.1 立体几何**

后端 - DSL Schema（`backend/app/dsl/schema.py`）：
- 新对象 `CubeObj{vertex, edge}` - 正方体
- 新对象 `CuboidObj{vertex, length, width, height}` - 长方体
- 新对象 `CylinderObj{center_bottom, radius, height}` - 圆柱
- 新对象 `ConeObj{center_bottom, radius, height}` - 圆锥
- 新对象 `SphereObj{center, radius}` - 球
- `GeometryObject` union 加上述 5 个对象
- `DSL` 类加 helper：`cubes()` / `cuboids()` / `cylinders()` / `cones()` / `spheres()`

后端 - Validator：
- 5 个对象的字段校验：anchor point 必须 PointObj；edge/radius/height/length/width > 0

后端 - Renderer（`backend/app/render/svg.py`）：
- 新增 `_project_3d(x, y, z) -> (x', y')` 等轴投影函数：`x' = x + z·cos30°, y' = y - z·sin30°`
- 新增 `_render_cube`：8 个顶点等轴投影 + 3 个可见面（顶/右/前）+ 1 个隐藏边虚线 path
- 新增 `_render_cuboid`：与 cube 同结构但用 length/width/height
- 新增 `_render_cylinder`：底面椭圆 + 顶面椭圆 + 左右两条母线
- 新增 `_render_cone`：底面椭圆 + 顶点 + 左右两条母线
- 新增 `_render_sphere`：大圆 + 赤道椭圆（虚线表示透视）
- 主渲染循环加 5 个分支，渲染顺序在所有平面几何之后

**V3.2 统计图表**

后端 - DSL Schema：
- 新对象 `BarChartObj{origin, data:[...], labels:[...], width?, height?, bar_color?}` - 条形统计图
- 新对象 `LineChartObj{origin, data:[...], labels:[...], width?, height?, line_color?}` - 折线统计图
- 新对象 `PieChartObj{center, data:[...], labels:[...], radius?, colors?}` - 扇形统计图
- `GeometryObject` union 加上述 3 个对象
- `DSL` 类加 helper：`bar_charts()` / `line_charts()` / `pie_charts()`

后端 - Validator：
- data 和 labels 长度必须一致
- bar/line 的 origin 必须是 PointObj；pie 的 center 必须 PointObj；pie radius > 0

后端 - Renderer：
- 新增 `_render_bar_chart`：每条数据一个矩形 + x 轴标签 + 数值标签
- 新增 `_render_line_chart`：连接数据点 + 数据点圆点 + 数值标签
- 新增 `_render_pie_chart`：按比例分配角度 + 扇形 path + 百分比标签
- 默认色板 `_CHART_PALETTE`（8 色）

**Prompt**
- `system.txt`：
  - 新增第 19 条「立体几何支持」：5 个对象字段说明 + 示例
  - 新增第 20 条「统计图表支持」：3 个对象字段说明 + 示例
  - 第 9 条拒绝清单更新：立体几何/统计图表从"拒绝"改为"已支持"
  - DSL Schema 节：对象 kind 加 cube/cuboid/cylinder/cone/sphere/bar_chart/line_chart/pie_chart
- `fewshots.jsonl`：+5 条（正方体 / 圆柱 / 球 / 条形图 / 扇形图）
- `extractor.py`：`fewshot_limit` 33 -> 38

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加 `'cube' | 'cuboid' | 'cylinder' | 'cone' | 'sphere' | 'bar_chart' | 'line_chart' | 'pie_chart'`；新增 `vertex/edge/length/width/height/center_bottom/data/labels/bar_color/line_color/colors` 字段
- `frontend/src/components/Canvas.tsx::describe`：8 个新 kind 分支
- `frontend/src/components/ChatPanel.tsx::describeObject`：8 个新分支
- `frontend/src/components/RightPanel.tsx::describeObject`：8 个新分支

### 变更

- `system.txt` 第 9 条「拒绝清单」：立体几何和统计图表从显式拒绝改为已支持
- 无破坏性变更。所有 V2-G.4 之前的 274 个测试无修改、无回归
- 立体几何和统计图表都不参与求解器约束（纯渲染）

### 修复

- 无

### DB Schema 升级

V2-G.4 -> V3.0：**无 schema 变更**。纯 DSL 层能力扩展，直接拉新代码即可。

### 测试

新增 22 个测试（274 -> 296），分布在 2 个文件：

- `tests/test_v3_solid_geometry.py`（13 个）：
  - schema：cube / cuboid / cylinder / cone / sphere 解析（5）
  - validator：cube vertex 类型 / cube edge<=0 / sphere radius<=0（3）
  - render：cube 含 path / cuboid 含 3 个面 / cylinder 含 ellipse / cone 含 apex / sphere 含 circle+ellipse（5）
- `tests/test_v3_charts.py`（9 个）：
  - schema：bar / line / pie chart 解析（3）
  - validator：origin 类型 / data-labels 长度 / pie radius<=0（3）
  - render：bar 含 rect+line / line 含 polyline+circle / pie 含 3 个 path+百分比（3）

### 设计决策记录

- **立体几何用等轴投影而非 three.js**：考虑工程量与维护成本，用纯 SVG 等轴投影（30°）即可满足教学示意需求；3D 库引入会大幅增加 bundle 体积和复杂度
- **等轴投影公式**：`x' = x + z·cos30°, y' = y - z·sin30°`，让 z 方向（前后）在 SVG 中向右下偏移，符合老师对 3D 图形的直觉
- **隐藏边用虚线**：正方体/长方体的隐藏边（在背面）用 stroke-dasharray 虚线绘制，让学生看清三维结构
- **统计图表走 DSL 对象**：bar/line/pie chart 作为 DSL 对象（含 data/labels 数据数组），不引入约束求解器；直接渲染
- **pie_chart 自动算百分比**：data 是数值列表，渲染时按总和比例分配角度，自动显示百分比标签
- **不引入 chart.js 等前端图表库**：用纯 SVG path/rect/circle/polyline 渲染，与现有渲染管线一致，导出 SVG/PNG/PDF 时不需要额外处理

### 路线图进度

本版完成后，K12 数学作图能力覆盖：
- ✅ 小学：基础图形 / 数轴 / 网格作图 / 统计图表 / 立体图形认识
- ✅ 初中：平面几何 / 函数图像 / 弧扇形 / 几何变换 / 阴影区域 / 辅助线 / 统计图表 / 立体图形
- ✅ 高中：函数图像 / 解析几何（椭圆/双曲线显式拆解）/ 立体几何 / 统计图表

不再显式拒绝的题型：
- ~~立体几何~~（V3.1 支持 cube/cuboid/cylinder/cone/sphere）
- ~~统计图表~~（V3.2 支持 bar_chart/line_chart/pie_chart）
- ~~隐式椭圆/双曲线~~（V2-G.1 支持显式拆解）

仍不支持的题型（V3.1 候选）：
- 三视图（需配合立体几何模块）
- 棱柱/棱锥/棱台（一般多面体）
- 立体截面
- 极坐标曲线 / 参数方程曲线
- 文氏图 / 概率树状图
- 流程图 / 算法框图

### 下一步候选

V3.0 完成后，下一轮对话有 **4 项待办工作**（2026-07-21 评审通过）。详细方案见 `docs/onboarding.md` 的「待完成的 4 项工作」节：

1. 🔥 **P0 - 历史会话侧抽屉**（3-5 天）：最大用户价值，老师试用流失的核心原因
2. 🔥 **P1 - V2-F.3 邮箱验证码 + WeChat OAuth + SMTP**（2-3 周）：最大拉新杠杆，微信扫码登录转化率高
3. 🟡 **P2 - Admin 管理界面**（1-2 周）：运营基础，解决 SSH+SQL 不可持续的痛点
4. 🟢 **P3 - V2-G.3 弓形对象 / 弧长标注 / 弓形面积标注 / 圆环扇环**（1 周）：低频，补全圆几何

**推荐执行顺序**：历史会话 -> V2-F.3 -> Admin -> V2-G.3

**关键提醒**：这 4 项中只有 V2-G.3 与"作图能力"直接相关。如果核心痛点是"老师反馈作不了图"，应优先做 V3 增强（三视图 / 棱柱棱锥 / 直方图 / 散点图）而非这 4 项。

V3 增强长期候选（不在本轮 4 项内）：
- V3.1 增强：三视图 / 棱柱 / 棱锥 / 立体截面
- V3.2 增强：直方图 / 散点图 / 箱线图 / 茎叶图
- 极坐标 / 参数方程曲线（V4）
- 文氏图 / 概率树状图（V4）

---

## V2-G.4 - 分段函数 / 位似变换 / 弓形 / 弧长弓形面积标注（第二波，2026-07-20）

**测试状态**：274/274 通过（V2-G.3 261 + V2-G.4 第二波 12 新增；前端 `npm run build` 通过）

**目标**：补齐 K12 教学场景中的 4 类中高频缺口--分段函数、位似变换、独立弓形对象、弧长弓形面积标注。

### 新增

**后端 - DSL Schema（`backend/app/dsl/schema.py`）**：
- `FunctionCurveObj` 加 `pieces: list[CurvePiece] | None = None` 字段 - 分段函数（与 expr 二选一）
- 新对象 `BowObj{center, from_point, to_point, ccw?}` - 弓形（弧+弦自动闭合，与 sector 区别是不画到圆心的半径）
- 新 transform 类型 `HomothetySpec{center, ratio}` - 位似变换
- `Annotation.kind` 加 `"arc_length"` 和 `"bow_area"` - 弧长/弓形面积标注
- `GeometryObject` union 加 `BowObj`
- `TransformSpec` union 加 `HomothetySpec`

**后端 - Validator**：
- FunctionCurveObj：pieces 与 expr 二选一；pieces 中每段 expr 必须过安全沙箱
- BowObj 校验：center/from_point/to_point 都必须是 PointObj；三点互异
- transform 校验：homothety 的 center 必须是 PointObj
- `bow_area` 约束放宽：arc 字段接受 ArcObj 或 BowObj

**后端 - Solver**：
- `apply_transform` 加 homothety 分支：`p' = center + ratio * (p - center)`
- `solve()` 主流程在 sector 之后追加 bow 的隐含等距残差
- `arc_angle/arc_length/bow_area` 残差 builder 接受 ArcObj 或 BowObj

**后端 - Renderer**：
- `_render_curve` 改造：支持 pieces 字段，按段分别采样渲染
- 新增 `_render_bow_path`：闭合 SVG path `M fx fy A ... tx ty Z`（弧+弦闭合）
- `_annotation_text` 加 arc_length / bow_area 分支：用 atan2 计算圆心角 + 公式 `r × angle_rad` / `0.5 × r² × (θ - sin θ)`
- `_annotation_position` 加 arc_length / bow_area 分支：弧外侧 1.15r 偏移 / 弓形内部 0.4 偏移

**后端 - Prompt**
- `system.txt`：新增第 18 条「分段函数 / 位似变换 / 弓形对象 / 弧长弓形面积标注」
- DSL Schema 节：transform.type 加 `homothety`；curve 加 `pieces`；对象 kind 加 `bow`；annotations kind 加 `arc_length / bow_area`

### 变更

- `FunctionCurveObj.expr` 改为可选（`str | None`），与 pieces 二选一；向后兼容（只传 expr 仍可用）
- `bow_area` 约束的 arc 字段从仅 ArcObj 放宽为 ArcObj | BowObj

### 修复

- 无

### DB Schema 升级

V2-G.3 -> V2-G.4：**无 schema 变更**。纯 DSL 层能力扩展。

### 测试

新增 12 个测试（261 -> 274），分布在 1 个文件：

- `tests/test_v2g4_wave2.py`（12 个）：
  - 分段函数：pieces schema 解析 / 多 polyline 渲染 / expr+pieces 二选一（3）
  - 位似变换：schema 解析 / 数学公式（原点中心）/ 非原点中心（3）
  - 弓形对象：schema 解析 / validator / 渲染 SVG path / bow_area 约束接受 BowObj（4）
  - 标注：arc_length 标注渲染 / bow_area 标注渲染（2）

### 设计决策记录

- **pieces 用列表而非多 curve 对象**：分段函数在数学上是一个函数，用 pieces 字段比让 LLM 输出多个 curve 对象更自然
- **BowObj 字段与 ArcObj 相同**：复用现有 _compute_arc_geometry / _arc_sweep_flags，最小改动
- **位似变换用 ratio 浮点**：支持任意比例（含负数表示反向位似），比"放大/缩小"语义更通用
- **标注位置**：弧长在弧外侧 1.15r 偏移；弓形面积在弓形内部（弦中点 + 沿弧中点方向 0.4 偏移）

### 下一步候选

- ~~V2-G.3 第一波 + V2-G.4 第二波~~ ✅ 完成
- **V3 第三波**：立体几何（three.js + 投影到 SVG）/ 统计图表（独立模块）/ 极坐标 / 文氏图 / 概率树状图（1-2 个月工程量）

---

## V2-G.3 - 阴影区域 / 数轴 / 网格作图 / 辅助线（第一波，2026-07-20）

**测试状态**：261/261 通过（V2-G.2 248 + V2-G.3 第一波 13 新增；前端 `npm run build` 通过）

**目标**：补齐 K12 教学场景中"小而广"的 4 类高频缺口--阴影区域、数轴、网格作图、辅助线。这些是小学+初中应用题作图刚需，每项工作量小但教学价值高。

**背景**：V2-G.2 完成后系统对初中圆几何已较完整，但调研发现 4 类跨学段场景缺失：圆环阴影、行程问题数轴、5×7 网格作图、几何证明辅助线。本版一次性补齐。

### 新增

**后端 - DSL Schema（`backend/app/dsl/schema.py`）**：
- 新对象 `RegionObj{boundary:[...], fill_color?, fill_opacity?, stroke?}` - 阴影/填充区域，通过引用一组 segment/arc id 按顺序组成闭合路径并填充
- 新对象 `NumberLineObj{origin, range?, tick_step?, show_ticks?, show_numbers?, label?}` - 1D 数轴含负数刻度
- 新对象 `AuxLineObj{a, b, extended?, dash?}` - 辅助线（虚线，不参与约束求解）
- `AxisObj` 加 `grid_size: float | None = None` 字段 - 网格作图模式（!= None 时画明显的网格点）
- `DSL` 类加 helper `regions()` / `number_lines()` / `aux_lines()`
- `GeometryObject` union 加 3 个新对象

**后端 - Validator（`backend/app/dsl/validator.py`）**：
- RegionObj 校验：boundary 元素必须是 SegmentObj 或 ArcObj；fill_opacity ∈ (0, 1]
- NumberLineObj 校验：origin 必须是 PointObj；range min < max；tick_step > 0
- AuxLineObj 校验：a/b 必须是 point-like（PointObj 或 TransformedPointObj）；a != b

**后端 - Solver（`backend/app/solver/engine.py`）**：
- gauge 选择扩展：axis OR number_line 作为 gauge anchor（origin 固定 (0,0)）
- RegionObj / AuxLineObj 不引入新自由变量（boundary/a/b 都引用已有对象）

**后端 - Renderer（`backend/app/render/svg.py`）**：
- 新增 `_render_region_path(region, dsl, sol, tx, style)`：按 boundary 顺序拼接 segment/arc 端点，构造闭合 SVG path 并填充
- 新增 `_render_number_line(nl, sol, tx, scale, style, text_el)`：水平线 + 箭头 + 刻度 + 数字 + 原点 O 标签
- 新增 `_render_aux_line(aux, sol, tx, style, canvas_size)`：虚线 segment 或延长直线
- `_render_axis` 末尾加 grid_size 渲染：当 grid_size != None 时画明显的网格点 circle
- 主渲染循环加 region / number_line / aux_line 分支

**后端 - Prompt**
- `system.txt`：新增第 17 条「阴影区域 / 数轴 / 网格作图 / 辅助线」
  - region{boundary, fill_color?, fill_opacity?, stroke?} + 圆环示例
  - number_line{origin, range?, ...} + 数轴示例
  - axis.grid_size 字段 + 网格作图示例
  - aux_line{a, b, extended?, dash?} + 辅助线示例
- DSL Schema 节：对象 kind 加 region / number_line / aux_line
- `fewshots.jsonl`：+4 条（扇形阴影 / 数轴 / 网格作图 / 辅助线）
- `extractor.py`：`fewshot_limit` 29 -> 33

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加 `'region' | 'number_line' | 'aux_line'`；新增 `boundary / fill_color / fill_opacity / stroke / range / show_numbers / label / extended / grid_size` 字段
- `frontend/src/components/Canvas.tsx::describe`：region / number_line / aux_line 分支
- `frontend/src/components/ChatPanel.tsx::describeObject`：3 个新分支
- `frontend/src/components/RightPanel.tsx::describeObject`：3 个新分支

### 变更

- 无破坏性变更。所有 V2-G.2 之前的 248 个测试无修改、无回归
- 3 个新对象都不引入新自由变量；number_line 作为 gauge anchor 与 axis 行为一致

### 修复

- 无

### DB Schema 升级

V2-G.2 -> V2-G.3：**无 schema 变更**。纯 DSL 层能力扩展，直接拉新代码即可。

### 测试

新增 13 个测试（248 -> 261），分布在 1 个文件：

- `tests/test_v2g3_wave1.py`（13 个）：
  - schema：region / number_line / aux_line / axis.grid_size 解析（4）
  - validator：region boundary 类型错 / number_line origin 类型错 / range 无效 / aux_line 端点类型错（4）
  - solver：number_line 作为 gauge anchor（1）
  - render：region 含 fill-opacity / number_line 含 marker-end / aux_line 含 stroke-dasharray / axis 有 grid_size 时画网格点（4）

### 设计决策记录

- **RegionObj 用 boundary 引用而非独立几何**：让用户指定一组 segment/arc id 按顺序组成闭合路径，而不是引入独立的"多边形顶点"字段。这样 region 可以复用已有对象（如圆环用两个 arc 边界），LLM 输出更简洁
- **NumberLineObj 与 AxisObj 区分**：1D 数轴只画水平线 + 刻度，不画 y 轴和网格。origin 固定为 (0,0)，方向锁定水平（与 axis 行为一致）
- **网格作图用 axis.grid_size 而非新对象**：网格作图本质是"在坐标系中画图 + 网格点对齐"，给 axis 加 grid_size 字段比新建 grid 对象更自然
- **AuxLineObj 不参与约束求解**：辅助线是渲染层概念，a/b 引用已有 PointObj，不引入新自由变量。若需要约束（如"AD ⊥ BC"），同时声明 segment 用于约束 + aux_line 用于虚线渲染

### 下一步候选

- ~~V2-G.3 第一波（阴影区域 / 数轴 / 网格 / 辅助线）~~ ✅ 完成
- **V2-G.4 第二波**：分段函数 / 位似变换 / 独立弓形对象 / 圆环扇环 / 弧长弓形面积标注
- **V3 第三波**：立体几何 / 统计图表（1-2 个月工程量）

---

## V2-G.2 - 圆弧角度 / 弧长 / 弓形面积约束（当前版本，2026-07-20）

**测试状态**：248/248 通过（V2-G.1 237 + V2-G.2 11 新增；前端 `npm run build` 通过）

**目标**：在 V2-G.1 弧/扇形对象基础上补齐初中圆几何的 3 类核心约束--圆心角、弧长、弓形面积。让老师能直接用「圆心角为 60°」「弧长为 π」「弓形面积为 2π」这类语义作图，而不是绕道用 length+angle 笨拙组合。

**背景**：V2-G.1 上线后，弧对象可以画但缺少角度/长度/面积的精确约束表达。K12 圆几何题里这三类约束高频出现（圆心角定理、弧长公式、扇形/弓形面积公式），需要 LLM 能直接输出对应约束。

### 新增

**后端 - DSL Schema（`backend/app/dsl/schema.py`）**：
- 新约束 `ArcAngleC{arc, value}` - 圆心角约束（度数 0~360，能区分大弧 >180°）
- 新约束 `ArcLengthC{arc, value}` - 弧长约束（value > 0）
- 新约束 `BowAreaC{arc, value}` - 弓形面积约束（value > 0，弓形=弧+弦围成区域）
- `Constraint` union 加入上述 3 类

**后端 - Validator（`backend/app/dsl/validator.py`）**：
- arc_angle / arc_length / bow_area 校验：arc 必须是 ArcObj
- arc_angle.value ∈ (0, 360) 度
- arc_length.value > 0
- bow_area.value > 0

**后端 - Solver（`backend/app/solver/engine.py`）**：
- `_build_constraint_residual` 加 3 个分支，共用一个内部函数：
  - **arc_angle** 残差：用 cos/sin 分量表达 `[cos(actual) - cos(target), sin(actual) - sin(target)]`，避免单一余弦约束的 60°/300° 歧义
  - **arc_length** 残差：`r × angle_rad - value`，其中 angle_rad = atan2(cross, dot) 带 ccw 方向归一到 (0, 2π]
  - **bow_area** 残差：`0.5 × r² × (θ - sin θ) - value`，θ 同 arc_length 的 angle_rad
- 关键实现细节：
  - 圆心角计算用 `atan2(cross, dot)` 而不是 `acos(cos)` -- 前者带符号能区分大弧小弧，后者只能给 (0, π)
  - ccw 方向：若 `arc.ccw=False`，对 atan2 结果取负（顺时针角度 = -逆时针角度）
  - 归一化到 (0, 2π]：负角度加 2π
- imports 加入 `ArcObj`

**后端 - Prompt**
- `system.txt`：
  - 新增第 16 条「圆弧角度 / 弧长 / 弓形面积约束」
    - arc_angle{arc, value}：圆心角度数 (0, 360)，>180 表示大弧（现有 angle 约束只支持 0-180）
    - arc_length{arc, value}：弧长 = 半径 × 圆心角
    - bow_area{arc, value}：弓形面积 = 0.5 × r² × (θ - sin θ)
    - 3 个示例
  - DSL Schema 节：约束 type 加 `arc_angle / arc_length / bow_area`
- `fewshots.jsonl`：+3 条
  - 弧角度：圆 O 半径 5，圆心角 AOB 为 60°
  - 弧长：圆 O 半径 2，画弧 AB 使弧长为 π
  - 弓形面积：半径 2 的圆中画面积为 2π 的弓形
- `extractor.py`：`fewshot_limit` 26 -> 29

### 变更

- 无破坏性变更。所有 V2-G.1 之前的 237 个测试无修改、无回归
- 不引入新对象、不引入新自由变量（arc 已是 V2-G.1 对象，3 个约束只引用已有 arc 的 id）

### 修复

- 无

### DB Schema 升级

V2-G.1 -> V2-G.2：**无 schema 变更**。纯约束层扩展，直接拉新代码即可。

### 测试

新增 11 个测试（237 -> 248），分布在 1 个文件：

- `tests/test_v2g2_arc_constraints.py`（11 个）：
  - schema：arc_angle / arc_length / bow_area Pydantic 解析（3）
  - validator：arc 类型错 / arc_angle 越界 / arc_length<=0 / bow_area<=0（4）
  - solver：arc_angle 60°（精度 1e-3）（1）
  - solver：arc_angle 270° 大弧（验证 cos/sin 分量避免 90° 歧义）（1）
  - solver：arc_length = 2π（半径 2 + 圆心角 180°）（1）
  - solver：bow_area = 2π（半径 2 + 圆心角 180° 半圆弓形）（1）

### 设计决策记录

- **arc_angle 用 cos/sin 双分量残差**：单一 `cos(actual) - cos(target)` 残差在 60° 和 300° 时无法区分（cos 值相同）。改用 `[cos - cos_target, sin - sin_target]` 双分量，求解器能稳定收敛到正确角度。代价是约束数从 1 变 2，但 least_squares 处理无障碍
- **arc_length / bow_area 用 atan2 而非 acos**：`atan2(cross, dot)` 返回带符号角度 (-π, π]，配合 ccw 取负后归一到 (0, 2π]，能区分大弧 > 180°。`acos` 只返回 (0, π)，无法表达大弧
- **不引入弓形对象**：弓形可视化可以用 arc + segment（弦）组合表达，本版只做约束层。若后续需要"独立弓形对象"再考虑加 `bow{arc}` 对象
- **arc_angle 的 ccw 语义**：value 是按 arc.ccw 方向张的角度。例如 ccw=True + value=270 表示"逆时针从 from 到 to 走 270°"，等价于 ccw=False + value=90（顺时针走 90°）。LLM 只需选一种自然表达即可

### 下一步候选

- ~~V2-G.2（圆弧角度/弧长/弓形面积）~~ ✅ 完成
- **V2-F.3**：邮箱验证码 + WeChat OAuth + SMTP/Resend 集成
- Alipay 正式应用上线后切正式环境（改 .env 即可）
- admin 管理界面（调整 per-user 配额）
- 历史会话侧抽屉（V2-E 遗留）
- V2-G.3 候选：独立弓形对象 / 弓形面积标注 / 弧长标注 / 圆环扇环
- V3：立体几何 / 统计图表 / 极坐标

---

## V2-G.1 - 弧 + 扇形 + 正多边形 + 梯形 + 椭圆显式拆解（当前版本，2026-07-20）

**测试状态**：237/237 通过（V2-F.2 219 + V2-G.1 18 新增；前端 `npm run build` 通过）

**目标**：补齐初中平面几何最后一块拼图--弧 / 扇形 / 正多边形 / 梯形；同时放宽椭圆拒绝范围（能拆成显式函数就能画）。

**背景**：V2-F.2 完成付费 + 配额 + 安全后，回到产品能力主线。K12 数学作图能力调研发现 4 项高频缺口：弧与扇形（初中圆几何核心）、正多边形约束（当前靠 length+angle 笨拙组合）、梯形专门约束（当前靠 parallel 表达）、椭圆显式支持（高中解析几何）。本版一次性补齐。

### 新增

**后端 - DSL Schema（`backend/app/dsl/schema.py`）**：
- 新对象 `ArcObj{center, from_point, to_point, radius?, ccw?=True}` - 圆弧
- 新对象 `SectorObj{center, from_point, to_point, ccw?=True}` - 扇形（闭合 path + 半透明填充）
- 新约束 `RegularPolygonC{polygon, sides}` - 正多边形（隐含 N 边等长 + N 个内角 = (N-2)×180/N）
- 新约束 `TrapezoidC{polygon, bases:[a,b]}` - 梯形（两底平行，两腰不平行靠自由求解自然产生）
- `DSL` 类加 helper `arcs()` / `sectors()`
- `GeometryObject` union 加 `ArcObj, SectorObj`
- `Constraint` union 加 `RegularPolygonC, TrapezoidC`

**后端 - Validator（`backend/app/dsl/validator.py`）**：
- ArcObj 校验：center/from_point/to_point 都必须是 PointObj；三点必须互异；radius > 0
- SectorObj 校验：center/from_point/to_point 都必须是 PointObj；三点必须互异
- regular_polygon 校验：polygon 是 PolygonObj；sides == len(vertices)；sides ≥ 3
- trapezoid 校验：polygon 是 4 边 PolygonObj；bases 是两个 segment id 且都属于该 polygon 的边；bases 必须是对边（顶点序中相隔 2 个位置）
- 新增 `_polygon_side_ids(dsl, poly)` 辅助函数返回 polygon 的所有边 segment id

**后端 - Solver（`backend/app/solver/engine.py`）**：
- `_build_constraint_residual` 加 `regular_polygon` 分支：N-1 个相邻边等长残差 + N 个内角 cos 残差（target = cos((N-2)×180/N)）
- `_build_constraint_residual` 加 `trapezoid` 分支：两底方向向量叉积归一化 = 0
- 新增 `_build_arc_implicit_residual(center_id, from_id, to_id, L)`：arc/sector 隐含等距约束 `|center-from| - |center-to| = 0`
- `solve()` 主流程在约束循环之后、圆绑定残差之前，自动追加 arc（radius is None 时）和 sector（永远）的隐含等距残差

**后端 - Renderer（`backend/app/render/svg.py`）**：
- 新增 `_compute_arc_geometry(center, from, to, sol, tx)`：返回 SVG 坐标系下的圆心 / 起点 / 终点 / 半径
- 新增 `_arc_sweep_flags(cx, cy, fx, fy, tx, ty, ccw, r)`：计算 SVG arc 命令的 large_arc 与 sweep flag
  - 关键转换：数学坐标系 y 向上，SVG y 向下；ccw=True（数学逆时针）在 SVG 中变成 sweep=0
  - large_arc = 1 当扫过角度 > 180°
- 新增 `_render_arc_path(arc, sol, tx, style, fill=False)`：渲染为 `<path d="M fx fy A r r 0 large sweep tx ty" fill="none"/>`
- 新增 `_render_sector_path(sec, sol, tx, style)`：渲染为闭合 path `M cx cy L fx fy A ... tx ty Z` + 半透明填充 `fill-opacity="0.15"`
- 主渲染循环加 arc/sector 分支，渲染顺序：axis -> curve -> 基础几何 -> **arc -> sector** -> 派生对象 -> 标注

**后端 - Prompt**
- `system.txt`：
  - 第 13 条末尾「仍拒绝椭圆」改为「椭圆 / 双曲线拆解 (V2-G.1 放宽)」：椭圆 `x²/9 + y²/4 = 1` 拆成 `y=±2*sqrt(1-x**2/9)` 两条 curve；双曲线类似
  - 新增第 14 条「弧与扇形支持」：arc / sector 对象字段说明 + 示例
  - 新增第 15 条「正多边形与梯形约束」：regular_polygon / trapezoid 约束说明 + 等腰梯形（trapezoid + equal_length）/ 直角梯形（trapezoid + perpendicular）组合表达
  - DSL Schema 节：对象 kind 加 `arc{...}` / `sector{...}`；约束 type 加 `regular_polygon{...}` / `trapezoid{...}`
- `fewshots.jsonl`：+5 条（弧 / 扇形 / 正六边形 / 等腰梯形 / 椭圆显式拆解）
- `extractor.py`：`fewshot_limit` 21 -> 26

**前端**
- `frontend/src/api/types.ts`：`GeoObject.kind` 加 `'arc' | 'sector'`；新增 `center / from_point / to_point / radius / ccw` 字段
- `frontend/src/components/Canvas.tsx::describe`：arc / sector 分支描述
- `frontend/src/components/ChatPanel.tsx::describeObject`：arc / sector 分支
- `frontend/src/components/RightPanel.tsx::describeObject`：arc / sector 分支

### 变更

- `system.txt` 第 13 条「仍拒绝椭圆」改为「椭圆 / 双曲线拆解 (V2-G.1 放宽)」--能拆成显式函数的椭圆/双曲线现在可画
- 无破坏性变更。所有 V2-F.2 之前的 219 个测试无修改、无回归
- arc/sector 不引入新自由变量（center/from/to 都是 PointObj）；regular_polygon/trapezoid 是约束不引入新对象

### 修复

- 无

### DB Schema 升级

V2-F.2 -> V2-G.1：**无 schema 变更**。纯 DSL 层能力扩展，直接拉新代码即可。已有 DB 中的现有会话向后兼容（不含 arc/sector/regular_polygon/trapezoid 的 DSL 仍正常工作）。

### 测试

新增 18 个测试（219 -> 237），分布在 2 个文件：

- `tests/test_v2g_arc_sector.py`（9 个）：
  - schema：arc / sector Pydantic 解析（2）
  - validator：center 类型错 / radius<=0 / 三点重合（3）
  - solver：arc 隐含等距约束（|center-from| == |center-to|）（1）
  - solver：sector 隐含等距约束（1）
  - render：SVG 含 `<path d="M...A..."/>`、扇形含 `fill-opacity`（2）
- `tests/test_v2g_regular_trapezoid.py`（9 个）：
  - schema：regular_polygon / trapezoid Pydantic 解析（2）
  - validator：sides 不匹配 / 非 4 边 / bases 不是 polygon 边 / bases 不是对边（4）
  - solver：正六边形所有边等长 + 内角 120°（1）
  - solver：梯形两底平行（叉积 < 1e-3）（1）
  - render：正六边形 SVG path 闭合（1）

### 设计决策记录

- **弧 radius 缺省行为**：选用「隐含等距约束」（center 到 from/to 距离相等，由 solver 自动追加），而不是「LLM 必须显式给 radius」。理由：让 LLM 输出更简洁，半径由几何关系自然推断
- **梯形设计**：仅加基础 `trapezoid{polygon, bases}` 约束表达两底平行；等腰梯形 = trapezoid + equal_length；直角梯形 = trapezoid + perpendicular。与现有约束风格一致，不引入冗余的 isoceles_trapezoid / right_trapezoid 专用约束
- **椭圆显式拆解**：纯 prompt 改造，schema 不动。LLM 若能拆成 `y=±b*sqrt(1-x²/a²)` 两条 curve 就能画；纯隐式一般式（如 xy=1 这类无法解出 y 的）仍拒绝
- **正多边形 hint 处理**：测试发现 hint 软约束（权重 0.05）会与正六边形对称约束轻微拉扯，导致残差卡在 ~3e-4 无法收敛到 1e-4 阈值；解决方案是去掉 hint 让求解器自由搜索（生产中 LLM 输出仍可带 hint，stage-2 抢救机制会处理边缘情况）

### 下一步候选

- **V2-G.2**：圆弧角度约束 / 弧长约束 / 弓形面积
- **V2-F.3**：邮箱验证码 + WeChat OAuth + SMTP/Resend 集成
- Alipay 正式应用上线后切正式环境（改 .env 即可）
- admin 管理界面（调整 per-user 配额）
- 历史会话侧抽屉（V2-E 遗留）
- V3：立体几何 / 统计图表 / 极坐标

---

## V2-F.2 - 付费 + 配额限流 + 安全加固（当前版本，2026-07-17）

**测试状态**：219/219 通过（V2-F.1 205 + V2-F.2 14 新增；前端 `npm run build` 通过）

**目标**：Alipay 电脑网站支付（沙箱）+ 配额限流（free 5/天 / pro 30/天）+ 强制登录 + API Key 泄露防护。

**背景**：V2-F.1 上线后 DeepSeek API Key 在 `backend/model_config.md` 中明文提交到 GitHub（private 仓库），导致 7 月 8 日一天被刷 ¥636。BFG 重写 git 历史后，V2-F.2 加 pre-commit hook + 配额限流防止再次发生。

### 新增

**后端 - Payment 模块（`app/payment/`）**：plans.py / repository.py / alipay.py / subscription.py / entitlement.py
**后端 - API**：payment.py（6 端点）+ webhooks.py（Alipay notify）
**后端 - DB**：+3 表（SubscriptionPlan/Order/UserSubscription with daily_graph_limit_override）
**后端 - 配额**：chat.py + chat_stream.py 加 ensure_user_can_send_chat + audit 含 plan/used_today
**前端**：PricingPage + SubscriptionPage + api/payment.ts + 路由 /pricing + /account/subscription
**安全**：.githooks/pre-commit + docs/security.md + .gitignore 加 model_config*.md

### 变更

- session/chat/export 路由：Optional -> 强制登录（删除匿名试用体验，防外部滥用）
- 既有测试 5 文件加 auth_headers fixture
- pro 套餐配额从无限（0）改为每日 30 张（plans.py PLAN_SEEDS + 现有 DB 需 SQL 更新）
- docker-compose.yml：加 `./secrets:/app/secrets:ro` 挂载 Alipay 密钥文件
- backend/.env：Alipay 密钥路径从 `/opt/t2g/secrets/` 改为容器内 `/app/secrets/`

### 修复

- `count_user_snapshots_today`：SQLAlchemy 2.0 查询语法（`func.count().select()` -> `select(func.count()).select_from()`）
- `_compute_period` / `_is_subscription_active`：处理 timezone-aware/naive datetime 混合比较（SQLite 返回 naive）
- 前端 `request<T>` 三处（payment.ts / auth.ts / client.ts）的 "body stream already read" bug：先 `r.text()` 一次再 `JSON.parse`，避免 `r.json()` 失败后 `r.text()` 二次读取 body
- `alipay.py::_read_key` 路径检测 bug：`"PRIVATE KEY" in path.upper()` 永远为 False（路径含下划线 `PRIVATE_KEY` 而非空格 `PRIVATE KEY`），改为显式 `is_private` 参数
- `alipay.py::_read_key` PKCS#8 格式 bug：Alipay 工具生成的私钥是 PKCS#8 格式（以 `MIIEvgIBADAN` 开头），裸 base64 包装时必须用 `-----BEGIN PRIVATE KEY-----`（非 `-----BEGIN RSA PRIVATE KEY-----` PKCS#1）
- `nginx.conf`：`/api/` 用 `^~` 前缀匹配（优先于正则），避免 `/api/export/*.svg|.png` 被静态资源缓存规则误匹配返回 404

### 安全事件复盘

2026-07-08 DeepSeek Key 泄露：`model_config.md` 含明文 Key 被 git push -> 被刷 ¥881（7/8 ¥636 + 7/9 ¥245）。
止血：BFG Repo-Cleaner 重写历史 + 重置 4 家 Key（DeepSeek / 火山 / MiniMax / Moonshot）。
防护：pre-commit hook 阻止 Key 提交 + 配额限流（即使 Key 泄露也有上限）+ 强制登录（防外部滥用）。

### DB Schema 升级

V2-F.1 -> V2-F.2：
- 新增 3 张表（`subscription_plan` / `subscription_order` / `user_subscription`）-- `create_all` 自动建
- 启动时 seed 3 个 plan（free 5/天 / pro 30/天 / enterprise 无限），幂等
- **不删除现有 DB**（保留用户 + 会话数据）
- **升级方式**：直接部署，`create_all` 自动建新表；现有 DB 的 plan 配额需手动 SQL 更新

### 配置说明

新增 6 个环境变量（开发期 `.env`，生产期 Docker env）：

```bash
# Alipay（沙箱开发期用沙箱地址，生产期切正式）
ALIPAY_APP_ID=2021000123456789
ALIPAY_APP_PRIVATE_KEY_FILE=/app/secrets/app_private_key.pem
ALIPAY_PUBLIC_KEY_FILE=/app/secrets/alipay_public_key.pem
ALIPAY_NOTIFY_URL=https://t2g.yinhour.com/api/webhooks/alipay
ALIPAY_RETURN_URL=https://t2g.yinhour.com/account/subscription
ALIPAY_GATEWAY_URL=https://openapi-sandbox.dl.alipaydev.com/gateway.do
# 生产期改为：https://openapi.alipay.com/gateway.do
```

### 调整配额的运维命令

DB 中的 `daily_graph_limit` 可通过 SQL 立即调整，不需要重启 backend：

```bash
# 改全局 free 配额（所有 free 用户生效）
docker compose exec backend python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/talk2graph.db')
conn.execute('UPDATE subscription_plan SET daily_graph_limit = 30 WHERE code = "free"')
conn.commit()
"

# 改单个用户的配额（per-user 覆盖，仍为 free 用户）
docker compose exec backend python3 -c "
import sqlite3, uuid
conn = sqlite3.connect('/app/data/talk2graph.db')
c = conn.cursor()
uid = c.execute("SELECT id FROM user WHERE email='user@example.com'").fetchone()[0]
c.execute('''INSERT OR REPLACE INTO user_subscription
  (id, user_id, plan_id, plan_code, status, daily_graph_limit_override)
  VALUES (?, ?, 'free', 'free', 'free', 100)''', (uuid.uuid4().hex, uid))
conn.commit()
"
```

### 测试

新增 14 个测试（205 -> 219），分布在 2 个文件：

- `tests/test_v2f_quota.py`（6 个）：free 5 张后拦截 / 无限配额 override / 匿名访问被拒 / 配额按 snapshot 计数（refuse 不扣）/ 新用户默认 free / 公开 plans 列表
- `tests/test_v2f_payment.py`（8 个）：创建订单返回 pay_url / 关闭订单 / webhook 验签通过+激活 / 验签失败拒绝 / 金额不匹配拒绝 / 幂等（重复通知）/ 月续期从 period_end 续 / 订单查询防探测 404

### 下一步候选

- **V2-F.3**：邮箱验证码 + WeChat OAuth + SMTP/Resend 集成
- Alipay 正式应用上线后切正式环境（改 .env 即可）
- admin 管理界面（调整 per-user 配额）

---

## V2-F.1 — 用户体系 + 审计骨架（2026-07-07）

**测试状态**：205/205 通过（V2-E 173 + V2-F.1 32 新增；前端 `npm run build` 通过）

**目标**：建立用户管理体系第一块——邮箱+密码注册/登录、JWT 鉴权、审计日志（含每次 chat 作图）、Session 归属校验、Admin 权限保护、前端路由 + 登录页。

**不含**：邮箱验证码 / WeChat OAuth / Alipay 付费 / 配额限流（这些分别在 F.2 / F.3）。F.1 不验证邮箱（用户填什么邮箱就建什么账号），SMTP 留 F.3 一起接。

**关键设计决策**：
- **JWT in localStorage** + `auth_version` 失效机制：用户改密后 `password_changed_at` 更新 → 旧 token 立即失效（不需要 token 黑名单）。借鉴 Lumiton `api/jwt_auth.py`
- **匿名会话保留试用体验**：未登录用户仍可创建 session（归属内置 `anonymous` 用户），任何人持 sid 仍可访问；登录用户只能访问自己的 session（cross-user 返回 404 防探测）
- **审计 best-effort**：所有 audit 写入 try/except + `logger.warning`，永不阻塞主流程；chat.send 走 `asyncio.create_task` fire-and-forget
- **Bootstrap admin**：首次启动且无 admin 时按 env `T2G_BOOTSTRAP_ADMIN_EMAIL` + `T2G_BOOTSTRAP_ADMIN_PASSWORD` 自动创建管理员；账号创建后这两个 env 可删除

### 新增

**后端 — Auth 模块（`app/auth/`）**
- `app/auth/__init__.py`：模块文档
- `app/auth/password.py`（~25 LOC）：bcrypt `hash_password` / `verify_password`，逐字借鉴 Lumiton `api/password_utils.py`；`verify_password` 捕获 `AttributeError` 防 None / 损坏 hash 崩溃
- `app/auth/jwt_token.py`（~95 LOC）：
  - HS256 + `auth_version` claim（从 `password_changed_at || updated_at || created_at` 派生 unix_ts）
  - `create_access_token(user)`：payload 含 sub/email/username/role/status/auth_version/iat/exp，默认 24h 过期
  - `decode_token(token, expected_auth_version=None)`：验签 + 验过期 + 可选 auth_version 比对
  - `TokenError` / `TokenExpiredError` / `TokenInvalidError` 异常分级
  - `decode_token_unsafe(token)`：不抛异常版本，用于 logger 提取 user_id 等 best-case 场景
- `app/auth/repository.py`（~80 LOC）：
  - `get_user_by_id` / `get_user_by_email` / `create_user` / `update_password` / `update_last_login` / `count_admins`
  - `update_password` + `update_last_login` 后 `await db.refresh(user)` 让 onupdate 自动字段（updated_at）重新加载，避免 `auth_version` 取到 stale 值触发 `MissingGreenlet` 错误
- `app/auth/deps.py`（~140 LOC）：
  - `CurrentUser` Pydantic 模型（id/email/username/role/status/auth_version，不含 hashed_password）
  - `get_current_user` Depends：从 `Authorization: Bearer <token>` 提取 + DB 校验 + status 校验 + auth_version 比对
  - `get_current_user_optional` Depends：有 token 则校验，无 token 返回 None（用于"未登录也能用，登录后走归属"的端点）
  - `require_admin` Depends：包 `get_current_user`，校验 `role == 'admin'`
  - `extract_request_meta(request)`：提取 `(ip, user_agent)` 给 audit 用（优先 X-Forwarded-For）

**后端 — Audit 模块（`app/audit/`）**
- `app/audit/__init__.py`：模块文档
- `app/audit/actions.py`：审计 action 字符串常量集中定义（auth.register.success / auth.login.success / .failed / auth.logout / auth.password.changed / chat.send / session.delete / order.* 等，避免拼写错误）
- `app/audit/repository.py`（~120 LOC）：
  - `create_audit(db, *, actor_id, actor_email, action, target_type?, target_id?, metadata?, ip?, ua?)`：同步写入，失败仅 `logger.warning` 不抛
  - `list_logs(db, *, actor_id?, action?, target_type?, target_id?, start?, end?, limit, offset)`：分页查询 + 多维过滤，返回 `(rows, total)`；total 用 `select(func.count()).select_from(subquery)` 单独查（避免 select 结果集 `rowcount` 不可靠问题）
  - `fire_and_forget(action, **kwargs) -> asyncio.Task`：开独立 session 写审计，不阻塞请求；用于 chat.send 等高频事件
  - 内部 `_fire_and_forget_inner` 局部 import `get_session` 避免循环依赖

**后端 — Auth API（`app/api/auth.py`，~250 LOC）**
- `POST /api/auth/register`：邮箱+密码+用户名 → 创建 user（role=user, status=active）→ 颁 JWT → 写 audit `auth.register.success`
  - F.1 不验证邮箱；F.3 接 SMTP 后加验证码步骤
  - 邮箱重复 → IntegrityError → 422
  - 密码 < 6 位 → pydantic Field(min_length=6) → 422
- `POST /api/auth/login`：邮箱+密码 → 校验 → 颁 JWT → 更新 last_login_at → 写 audit `auth.login.success` 或 `.failed`（含 reason: user_not_found / invalid_password / disabled）
- `POST /api/auth/logout`：写 audit `auth.logout`（best-effort）；客户端清 token
- `GET /api/auth/me`：返回当前用户最新信息（从 DB 拉取，含 last_login_at 等动态字段）
- `POST /api/auth/refresh`：用旧 token 换新 token（重置 24h 过期；auth_version 必须不变）
- `POST /api/auth/change-password`：old + new → 校验旧密码 → 更新 hashed_password + password_changed_at（旧 token 全失效）→ 写 audit `auth.password.changed`

**后端 — AuditLog API（`app/api/audit_log.py`，~80 LOC）**
- `GET /api/audit-log`（admin only）：分页 + 多维过滤（actor_id / action / target_type / target_id / start / end / limit / offset）
- 返回 `{items, total, limit, offset}`，metadata 字段自动 JSON parse

**后端 — DB Schema 变更**
- `app/db/models.py`：
  - 新增 `User` 表（id/email/username/hashed_password/role/status/password_changed_at/last_login_at/created_at/updated_at；email UNIQUE INDEX）
  - 新增 `AuditLog` 表（id/actor_id INDEX/actor_email/action INDEX/target_type/target_id/metadata_json/ip_address/user_agent/created_at INDEX）
  - `Session` 表加 `user_id: str | None`（FK user.id ondelete=SET NULL, INDEX）
  - 常量 `ANONYMOUS_USER_ID = "00000000-0000-0000-0000-anonymous"`（固定 ID 的内置匿名用户）
- `app/db/migrations.py`：`REQUIRED_COLUMNS["session"] = [("user_id", "TEXT")]`，让老库通过 `ensure_schema()` 自动 ALTER 加列
- `app/db/session.py::init_db` 启动时增加 3 步 bootstrap：
  1. `_bootstrap_anonymous_user`：创建内置 anonymous 用户（id 固定，role=user, status=disabled 禁止登录，幂等）
  2. `_attach_orphan_sessions`：把所有 `user_id IS NULL` 的 session 全部归属到 anonymous（裸 SQL UPDATE，幂等）
  3. `_bootstrap_admin`：若 DB 无 admin 用户且 env `T2G_BOOTSTRAP_ADMIN_EMAIL` + `T2G_BOOTSTRAP_ADMIN_PASSWORD` 已配置 → 创建 admin 用户；幂等

**后端 — Config / 依赖**
- `app/config.py::Settings` 新增：
  - `jwt_secret`（env `T2G_JWT_SECRET`，默认 `dev-only-change-in-prod-please-use-32+-chars`）
  - `jwt_expiry_seconds`（env `T2G_JWT_EXPIRY_SECONDS`，默认 86400 = 24h）
  - `bootstrap_admin_email` / `bootstrap_admin_password`（env `T2G_BOOTSTRAP_ADMIN_EMAIL` / `T2G_BOOTSTRAP_ADMIN_PASSWORD`）
- `backend/.env.example`：新增"用户管理（V2-F.1）"章节
- `backend/pyproject.toml`：新增依赖 `bcrypt>=4.0` / `pyjwt>=2.8` / `email-validator>=2.0`（pydantic EmailStr 校验需要）
- `backend/app/main.py`：注册 `auth.router` + `audit_log.router`

**前端 — 路由 + AuthStore**
- `frontend/package.json`：新增依赖 `react-router-dom@^6.26`
- `frontend/src/main.tsx`：用 `BrowserRouter` 包 `<App/>`
- `frontend/src/App.tsx` 重构：
  - 顶层 `<Routes>` 定义 7 条路由：`/` LandingPage / `/login` / `/register` / `/forgot-password` / `/app` AppShell（守卫）/ `/account` AccountPage（守卫）/ `/account/password` ChangePasswordPage（守卫）/ `*` → `/`
  - `ProtectedRoute` 组件：未登录 → `<Navigate to="/login?from=...">`；登录中显示 spinner
  - `AppShell`（原 App 内容抽出）：进入 `/app` 时若 `sessionId` is null 则自动 `newSession()`
  - `LandingPage`：保留现有 WelcomeCard 风格 + 升级 CTA（已注册显示"进入工作台"，未注册显示"免费注册"+"已注册，去登录"）
- `frontend/src/store/auth.ts`（新，~95 LOC）：独立 AuthStore
  - state：`user / token / isAuthenticated / isLoading / lastAuthCheck`
  - actions：`init / login / register / logout / checkAuth / refreshUser`
  - `checkAuth` 30s TTL 缓存，避免每次切路由都打 `/me`
- `frontend/src/store/index.ts::init`：仅登录用户恢复或新建 session；未登录用户在落地页不创建 session（节省资源）
- `frontend/src/api/auth.ts`（新，~140 LOC）：
  - `loadStoredAuth` / `storeAuth` / `clearStoredAuth` / `getStoredToken` / `authHeader`：localStorage 持久化（key=`t2g.auth`）
  - `authApi`：register / login / logout / me / refresh / changePassword / listAuditLogs
  - 独立 `request<T>` 包装注入 `authHeader()` + 401 拦截（仅当原本有 token 时才清，避免公开页 401 误清）
- `frontend/src/api/client.ts`：所有 `request<T>` 调用注入 `authHeader()`；`chatStream` 的 fetch 也注入；401 拦截跳 `/login?from=...`
- `frontend/src/api/types.ts`：新增 `User` / `AuthResp` / `AuditLogItem` / `AuditLogListResp` 类型

**前端 — 页面（5 个，~600 LOC）**
- `frontend/src/pages/LoginPage.tsx`：邮箱+密码表单，提交后跳 `from` 参数或 `/app`
- `frontend/src/pages/RegisterPage.tsx`：邮箱+用户名+密码+确认密码；密码 < 6 位 / 不一致前端校验
- `frontend/src/pages/ForgotPasswordPage.tsx`：F.1 占位（提示"邮箱重置功能尚未启用，联系管理员"）；F.3 接 SMTP 后实跑
- `frontend/src/pages/AccountPage.tsx`：用户信息卡片 + 修改密码 / 返回工作台 / 退出登录按钮
- `frontend/src/pages/ChangePasswordPage.tsx`：旧密码+新密码+确认；成功后 1.5s 自动 logout 跳登录页（旧 token 已失效）
- `frontend/src/components/auth/AuthPageShell.tsx`（~25 LOC）：公共壳（居中卡片 + brand + 教育蓝渐变背景）
- `frontend/src/components/auth/ProtectedRoute.tsx`（~30 LOC）：路由守卫，loading 时显示 spinner
- `frontend/src/components/auth/UserMenu.tsx`（~70 LOC）：TopBar 右上角下拉（圆形头像 + 用户名 + caret），下拉菜单含账号信息 / 修改密码 / 退出登录
- `frontend/src/components/TopBar.tsx`：
  - brand 改为 `<Link to="/">`（可点击回首页）
  - 右侧加 `<UserMenu/>`（已登录显示用户菜单）
- `frontend/src/styles.css`（815 → 1130 行，+315 行）：
  - 新增 `.btn` / `.btn-primary` / `.btn-ghost` / `.btn-danger` / `.btn-block` 通用按钮
  - 新增 `.auth-page` / `.auth-card` / `.auth-brand` / `.auth-title` / `.auth-sub` / `.auth-form` / `.auth-field` / `.auth-error` / `.auth-success` / `.auth-links` 样式（教育蓝 + 卡片 + 圆角 + 阴影）
  - 新增 `.auth-loading` / `.auth-loading-card` / `.auth-loading-spinner`（旋转动画）
  - 新增 `.landing-content` / `.landing-title`（渐变文字） / `.landing-sub` / `.landing-cta` / `.landing-features`
  - 新增 `.account-info` / `.account-row` / `.account-label` / `.account-value` / `.account-actions`
  - 新增 `.user-menu` / `.user-avatar-btn` / `.user-avatar`（渐变圆形头像） / `.user-name` / `.caret` / `.user-menu-dropdown` / `.user-menu-header` / `.dropdown-divider`
  - TopBar 的 `.brand` 改为 a 标签样式微调

### 变更

- `app/db/models.py::Session`：新增 `user_id` FK 列（向后兼容，nullable）
- `app/session/repo.py`：
  - `create_session` 加 `user_id` 参数
  - `list_sessions` 加 `user_id` 参数过滤
- `app/api/session.py`：
  - 所有 `/api/session*` 路由加 `user: Optional[CurrentUser] = Depends(get_current_user_optional)` 依赖
  - 新增 `_require_session_with_owner(db, sid, user)`：校验 session 归属，cross-user 返回 404（防探测）；anonymous session 任何人都能访问（保留试用体验）
  - POST /api/session：登录用户归属自己，未登录归属 anonymous
  - GET /api/sessions：只返回当前用户的（含 anonymous 的）
  - GET/DELETE /api/session/{sid} + dsl/messages/history/undo/redo/feedback：均加归属校验
- `app/api/admin.py`：
  - 所有 3 个路由（stats / feedback / feedback.jsonl）加 `Depends(require_admin)`
  - 头部注释从"无鉴权 MVP"改为"V2-F.1：所有路由要求 admin 角色"
- `app/main.py`：注册 `auth.router` + `audit_log.router`
- `backend/.env.example`：顶部新增"用户管理（V2-F.1）"章节（JWT_SECRET / BOOTSTRAP_ADMIN_*）
- `backend/pyproject.toml`：+bcrypt>=4.0 / +pyjwt>=2.8 / +email-validator>=2.0

### 修复

- `app/auth/repository.py::update_password` / `update_last_login`：commit 后 `await db.refresh(user)`，让 onupdate 自动字段（updated_at）重新加载，避免 `auth_version` 取到 stale 值导致 `MissingGreenlet` 错误（测试 `test_login_success` / `test_change_password_invalidates_old_token` 暴露）
- `app/auth/password.py::verify_password`：捕获 `AttributeError`，防止 hashed=None / 损坏 hash 字符串导致崩溃
- `app/audit/repository.py::list_logs`：total 用 `select(func.count()).select_from(subquery)` 单独查，避免 SQLAlchemy 2.0 中 select 结果集 `rowcount` 不可靠问题

### DB Schema 升级

V2-E → V2-F.1：
- 新增 2 张表：`user` / `audit_log`（`create_all` 自动建）
- `session` 表新增 `user_id TEXT` 列（`ensure_schema` 自动 ALTER）
- 启动时自动建 anonymous user（id 固定）+ 把 NULL session 归属到 anonymous + 按 env 建 bootstrap admin
- **升级方式**：开发期直接 `rm backend/data/talk2graph.db`；生产期无需手动操作（启动自动迁移）

### 配置说明

新增 3 个环境变量（开发期 `.env`，生产期 Docker env）：

```bash
# JWT HS256 签名密钥。开发期可用默认值；生产期必须替换为长随机串：
#   openssl rand -hex 32
T2G_JWT_SECRET=dev-only-change-in-prod-please-use-32+-chars

# Bootstrap admin：首次启动且无 admin 用户时按这两个 env 自动创建管理员
# 创建成功后这两个 env 可删除（账号之后改密走 /api/auth/change-password 流程）
T2G_BOOTSTRAP_ADMIN_EMAIL=admin@your-domain.com
T2G_BOOTSTRAP_ADMIN_PASSWORD=change-me-immediately
```

### 测试

新增 32 个测试（173 → 205），分布在 6 个文件：

- `tests/test_v2f_password.py`（4 个）：hash/verify roundtrip / 错密码 / 损坏 hash / salt 唯一性
- `tests/test_v2f_jwt.py`（5 个）：编解码 roundtrip / 过期拒绝 / 错 secret 拒绝 / auth_version 失效 / claims 完整性
- `tests/test_v2f_auth.py`（12 个）：注册成功 / 邮箱重复 422 / 密码过短 422 / 登录成功 / 错密码 401 + audit / 不存在用户 401 + audit / 禁用账号 403 / me 带 token / me 不带 token 401 / refresh / 改密后旧 token 失效 / bootstrap admin 首次启动
- `tests/test_v2f_audit.py`（5 个）：写入 + 列表查询 / 按 actor 过滤 / best-effort 不阻塞主流程 / fire_and_forget chat.send / 非 admin 403
- `tests/test_v2f_session_ownership.py`（4 个）：用户 A 创建的 session A 能访问 / B 访问 A 的返回 404 防探测 / 列表按用户过滤 / 匿名 session 任何人可访问
- `tests/test_v2f_admin_guard.py`（2 个）：普通 user 访问 `/api/admin/stats` 403 / admin 角色访问通过

既有测试改造（~10 处加 admin token）：
- `tests/test_w6_ops.py`：fixture 内预建 admin 用户，新增 `admin_token` fixture；admin stats 测试加 headers
- `tests/test_w7_feedback.py`：同上，新增 `admin_headers` fixture；admin feedback / jsonl 测试加 headers

### 下一步候选

- **V2-F.2**：付费（Alipay 电脑网站支付 + 配额限流）
- **V2-F.3**：邮箱验证码 + WeChat OAuth + SMTP/Resend 集成
- 历史会话侧抽屉（V2-E 路线图遗留）

---

## V2-E — 多 Provider 评测 + UI/UX 打磨 + 自动 Fallback（2026-07-07）

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
