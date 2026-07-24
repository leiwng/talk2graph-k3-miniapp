import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { useAuthStore } from '../store/auth'
import { authApi } from '../api/auth'

export function RegisterPage() {
  const navigate = useNavigate()
  const register = useAuthStore((s) => s.register)
  const login = useAuthStore((s) => s.login)

  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [sendingCode, setSendingCode] = useState(false)
  const [registered, setRegistered] = useState(false)
  const [resendCountdown, setResendCountdown] = useState(0)

  const startCountdown = () => {
    setResendCountdown(60)
    const timer = setInterval(() => {
      setResendCountdown((n) => {
        if (n <= 1) {
          clearInterval(timer)
          return 0
        }
        return n - 1
      })
    }, 1000)
  }

  const onSendCode = async () => {
    setError(null)
    setInfo(null)
    if (!email.trim()) {
      setError('请先填写邮箱')
      return
    }
    setSendingCode(true)
    try {
      const r = await authApi.sendVerificationCode(email.trim(), 'register')
      if (r.sent) {
        setInfo('验证码已发送到邮箱，15 分钟内有效')
        startCountdown()
      } else {
        setError(r.message || '验证码发送失败')
      }
    } catch (err: any) {
      // 429 视为已发送
      if (err.code === 'rate_limited' || err.message?.includes('60')) {
        setInfo('已发送，请稍候再试')
        startCountdown()
      } else {
        setError(err.message || '验证码发送失败')
      }
    } finally {
      setSendingCode(false)
    }
  }

  const onRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)
    if (!email.trim() || !password.trim() || !username.trim()) {
      setError('请填写邮箱、用户名和密码')
      return
    }
    if (password.length < 6) {
      setError('密码至少 6 位')
      return
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setSubmitting(true)
    try {
      await register(email.trim(), password, username.trim())
      setRegistered(true)
      setInfo('注册成功！验证码已发送到邮箱，请输入验证码完成验证')
      startCountdown()
    } catch (err: any) {
      setError(err.message || '注册失败')
    } finally {
      setSubmitting(false)
    }
  }

  const onVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)
    if (!code.trim() || code.trim().length !== 6) {
      setError('请输入 6 位验证码')
      return
    }
    setSubmitting(true)
    try {
      await authApi.verifyEmail(email.trim(), code.trim())
      // 验证成功 -> 重新登录拿含 email_verified=true 的 token
      await login(email.trim(), password)
      navigate('/app', { replace: true })
    } catch (err: any) {
      setError(err.message || '验证失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">注册新账号</h2>
      <p className="auth-sub">免费开始使用，每天 5 张图</p>

      {!registered ? (
        <form className="auth-form" onSubmit={onRegister}>
          <label className="auth-field">
            <span>邮箱</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus
            />
          </label>
          <label className="auth-field">
            <span>用户名</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="如何称呼你"
              autoComplete="username"
            />
          </label>
          <label className="auth-field">
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="至少 6 位"
              autoComplete="new-password"
            />
          </label>
          <label className="auth-field">
            <span>确认密码</span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="再输一次"
              autoComplete="new-password"
            />
          </label>

          {error && <div className="auth-error">{error}</div>}
          {info && <div className="auth-success">{info}</div>}

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? '注册中…' : '注册'}
          </button>

          <div className="auth-links">
            <Link to="/login">已有账号，去登录</Link>
          </div>
        </form>
      ) : (
        <form className="auth-form" onSubmit={onVerify}>
          <div className="auth-info-text">
            已向 <strong>{email}</strong> 发送验证码。<br />
            请输入验证码完成邮箱验证。
          </div>
          <label className="auth-field">
            <span>验证码</span>
            <div className="auth-code-row">
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="6 位数字"
                maxLength={6}
                autoFocus
                inputMode="numeric"
              />
              <button
                type="button"
                onClick={onSendCode}
                disabled={sendingCode || resendCountdown > 0}
                className="btn btn-ghost auth-code-btn"
              >
                {resendCountdown > 0 ? `${resendCountdown}s` : '重新发送'}
              </button>
            </div>
          </label>

          {error && <div className="auth-error">{error}</div>}
          {info && <div className="auth-success">{info}</div>}

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? '验证中…' : '完成验证'}
          </button>

          <div className="auth-links">
            <Link to="/login">跳过验证，先去登录</Link>
          </div>
        </form>
      )}
    </AuthPageShell>
  )
}
