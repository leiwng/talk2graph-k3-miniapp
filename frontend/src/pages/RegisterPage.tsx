import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { useAuthStore } from '../store/auth'

export function RegisterPage() {
  const navigate = useNavigate()
  const register = useAuthStore((s) => s.register)

  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
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
      navigate('/app', { replace: true })
    } catch (err: any) {
      setError(err.message || '注册失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">注册新账号</h2>
      <p className="auth-sub">免费开始使用，每天 5 张图</p>

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

        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? '注册中…' : '注册'}
        </button>

        <div className="auth-links">
          <Link to="/login">已有账号，去登录</Link>
        </div>
      </form>
    </AuthPageShell>
  )
}
