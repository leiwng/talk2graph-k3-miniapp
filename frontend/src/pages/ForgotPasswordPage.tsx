import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { authApi } from '../api/auth'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!email.trim()) {
      setError('请填写邮箱')
      return
    }
    setSubmitting(true)
    try {
      await authApi.forgotPassword(email.trim())
      setSubmitted(true)
    } catch (err: any) {
      setError(err.message || '发送失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">找回密码</h2>
      <p className="auth-sub">通过邮箱重置链接重置密码</p>

      {submitted ? (
        <div className="auth-success">
          <p>✓ 如果该邮箱已注册，重置链接已发送。</p>
          <p className="auth-hint">
            请登录邮箱查收邮件，点击邮件中的链接完成密码重置。<br />
            链接 30 分钟内有效。
          </p>
          <Link to="/login" className="btn btn-ghost btn-block">返回登录</Link>
        </div>
      ) : (
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
          {error && <div className="auth-error">{error}</div>}
          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? '发送中…' : '发送重置链接'}
          </button>
          <div className="auth-links">
            <Link to="/login">返回登录</Link>
          </div>
        </form>
      )}
    </AuthPageShell>
  )
}
