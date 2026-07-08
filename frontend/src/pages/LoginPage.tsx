import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { useAuthStore } from '../store/auth'

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const login = useAuthStore((s) => s.login)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // 已登录则跳走
  if (isAuthenticated) {
    const from = searchParams.get('from') || '/app'
    navigate(from, { replace: true })
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!email.trim() || !password.trim()) {
      setError('请填写邮箱和密码')
      return
    }
    setSubmitting(true)
    try {
      await login(email.trim(), password)
      const from = searchParams.get('from') || '/app'
      navigate(from, { replace: true })
    } catch (err: any) {
      setError(err.message || '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">欢迎回来</h2>
      <p className="auth-sub">登录后即可继续画图</p>

      <form className="auth-form" onSubmit={onSubmit}>
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
          <span>密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••"
            autoComplete="current-password"
          />
        </label>

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? '登录中…' : '登录'}
        </button>

        <div className="auth-links">
          <Link to="/forgot-password">忘记密码？</Link>
          <span>·</span>
          <Link to="/register">注册新账号</Link>
        </div>
      </form>
    </AuthPageShell>
  )
}
