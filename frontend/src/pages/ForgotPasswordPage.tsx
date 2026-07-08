import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!email.trim()) {
      setError('请填写邮箱')
      return
    }
    // V2-F.1：暂未接 SMTP，仅占位提示
    setSubmitted(true)
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">找回密码</h2>
      <p className="auth-sub">通过邮箱验证码重置</p>

      {submitted ? (
        <div className="auth-success">
          <p>✓ 如果该邮箱已注册，重置链接已发送。</p>
          <p className="auth-hint">
            V2-F.1 阶段邮箱重置功能尚未启用，
            如需重置密码请联系管理员。
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
          <button type="submit" className="btn btn-primary btn-block">发送重置链接</button>
          <div className="auth-links">
            <Link to="/login">返回登录</Link>
          </div>
        </form>
      )}
    </AuthPageShell>
  )
}
