import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { authApi } from '../api/auth'

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!token) {
      setError('重置链接无效')
      return
    }
    if (newPassword.length < 6) {
      setError('密码至少 6 位')
      return
    }
    if (newPassword !== confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setSubmitting(true)
    try {
      await authApi.resetPassword(token, newPassword)
      setInfo('密码已重置，即将跳转登录页')
      setTimeout(() => navigate('/login', { replace: true }), 1500)
    } catch (err: any) {
      setError(err.message || '重置失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">重置密码</h2>
      <p className="auth-sub">设置新的登录密码</p>

      <form className="auth-form" onSubmit={onSubmit}>
        <label className="auth-field">
          <span>新密码</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="至少 6 位"
            autoComplete="new-password"
            autoFocus
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

        <button type="submit" className="btn btn-primary btn-block" disabled={submitting || !token}>
          {submitting ? '重置中…' : '重置密码'}
        </button>

        <div className="auth-links">
          <Link to="/login">返回登录</Link>
        </div>
      </form>
    </AuthPageShell>
  )
}
