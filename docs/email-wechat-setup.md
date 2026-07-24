# 邮件 + 微信 OAuth 切换指南

> 上线前必读：把开发期的 ConsoleProvider（仅打日志）切到生产环境的真实邮件发送；微信 OAuth 填入正式 AppID/Secret。

## 一、邮件 Provider 切换

### 1. ConsoleProvider（开发期默认）

仅打日志，不发真实邮件。老师收不到验证码。

```bash
EMAIL_PROVIDER=console
```

### 2. SMTPProvider（生产期推荐）

适用任何标准 SMTP 服务器：

| Provider | SMTP_HOST | SMTP_PORT | SMTP_USE_TLS |
|---|---|---|---|
| 飞书企业邮箱（推荐） | `smtp.feishu.cn` | 465 | true |
| 腾讯企业邮箱 | `smtp.exmail.qq.com` | 465 | true |
| 阿里云邮件推送 | `smtpdm.aliyun.com` | 465 | true |
| Gmail | `smtp.gmail.com` | 465 | true（需应用专用密码） |

#### 飞书企业邮箱 SMTP 切换步骤

1. 飞书管理后台 → 邮件 → 客户端配置，确认 SMTP 已开通
2. 创建应用专用密码（飞书后台 → 账号 → 安全设置 → 应用专用密码）
3. 改 `.env`：
   ```bash
   EMAIL_PROVIDER=smtp
   SMTP_HOST=smtp.feishu.cn
   SMTP_PORT=465
   SMTP_USERNAME=noreply@your-domain.feishu.cn
   SMTP_PASSWORD=<应用专用密码>
   SMTP_USE_TLS=true
   EMAIL_FROM=noreply@your-domain.feishu.cn
   ```
4. 重启 backend：`docker compose up -d backend --build`
5. 测试：注册一个新用户，确认能收到验证码邮件

### 3. ResendProvider（备选）

免费 3000 封/月，5 分钟接入。生产期用自有域名配 SPF/DKIM 后送达率高。

```bash
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=noreply@your-domain.com   # 自有域名；免费版用 onboarding@resend.dev
```

## 二、密码重置链接配置

前端路由 `/reset-password` 默认相对路径。生产期改成完整 URL：

```bash
PASSWORD_RESET_BASE_URL=https://t2g.yinhour.com/reset-password
```

老师收到的重置邮件链接会是 `https://t2g.yinhour.com/reset-password?token=xxx`。

## 三、微信开放平台 PC 扫码登录

### 前置条件

- 微信开放平台账号（https://open.weixin.qq.com/）
- 已审核通过的「网站应用」（需企业资质）
- 配置回调域名：`https://t2g.yinhour.com`

### 切换步骤

1. 微信开放平台 → 网站应用 → 查看 AppID 和 AppSecret
2. 改 `.env`：
   ```bash
   WECHAT_APP_ID=wx你的AppID
   WECHAT_APP_SECRET=你的AppSecret
   WECHAT_REDIRECT_URI=https://t2g.yinhour.com/api/auth/wechat/callback
   WECHAT_FRONTEND_REDIRECT_URL=https://t2g.yinhour.com/wechat/callback
   ```
3. 微信开放平台 → 网站应用 → 授权回调域 → 填 `t2g.yinhour.com`
4. 重启 backend
5. 测试：登录页点「微信扫码登录」→ 弹微信二维码 → 扫码确认 → 自动登录跳 /app

### 代码已就绪

V3.2 P1 已完整实现：
- 后端：`app/auth/wechat.py`（OAuth 流程）+ `GET /api/auth/wechat/login-url` + `GET /api/auth/wechat/callback`
- 前端：`WechatCallbackPage.tsx` + LoginPage 微信按钮
- 测试：`tests/test_p1_email_wechat.py::test_wechat_login_url`

拿到 AppID/Secret 后**只需改 .env + 重启**，不需要改代码。

## 四、上线前检查清单

- [ ] 邮件 Provider 切到 SMTP / Resend（非 console）
- [ ] `EMAIL_FROM` 是可信发件人地址
- [ ] `PASSWORD_RESET_BASE_URL` 改成完整生产 URL
- [ ] 跑一次「忘记密码」端到端测试，确认邮件能收到 + 链接能跳转
- [ ] 微信开放平台 AppID/Secret 已填入 .env
- [ ] 微信授权回调域已配置
- [ ] 跑一次微信扫码登录端到端测试

## 五、故障排查

### 邮件发不出去

1. 检查 `EMAIL_PROVIDER` 是不是 `console`（默认）→ 改成 `smtp` 或 `resend`
2. 检查 backend 日志：`docker compose logs backend | grep email`
3. SMTP 凭据错误会显示 `SMTP send failed: ...`
4. 飞书应用专用密码可能过期 → 飞书后台重新生成

### 微信扫码登录失败

1. 检查 `WECHAT_APP_ID` / `WECHAT_APP_SECRET` 是否填了
2. 检查回调域名是否与 `WECHAT_REDIRECT_URI` 一致
3. 后端日志看 `wechat oauth failed: ...`
4. 微信开放平台审核状态：必须是「已通过」状态才能用

### 重置链接打不开

1. 检查 `PASSWORD_RESET_BASE_URL` 是否完整 URL
2. 检查前端路由 `/reset-password` 是否能访问
