import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/auth'

export function ChangePasswordPage() {
  const navigate = useNavigate()
  const refreshUser = useAuthStore((s) => s.refreshUser)
  const logout = useAuthStore((s) => s.logout)

  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!oldPwd || !newPwd) {
      setError('请填写旧密码和新密码')
      return
    }
    if (newPwd.length < 6) {
      setError('新密码至少 6 位')
      return
    }
    if (newPwd !== confirm) {
      setError('两次输入的新密码不一致')
      return
    }
    setSubmitting(true)
    try {
      await authApi.changePassword(oldPwd, newPwd)
      setSuccess(true)
      // 改密成功后旧 token 失效，需要重新登录
      setTimeout(() => {
        void logout().then(() => navigate('/login', { replace: true }))
      }, 1500)
    } catch (err: any) {
      setError(err.message || '修改失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageShell>
      <h2 className="auth-title">修改密码</h2>
      <p className="auth-sub">修改后需要重新登录</p>

      {success ? (
        <div className="auth-success">
          <p>✓ 密码已修改，正在跳转登录页…</p>
        </div>
      ) : (
        <form className="auth-form" onSubmit={onSubmit}>
          <label className="auth-field">
            <span>旧密码</span>
            <input
              type="password"
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
              autoComplete="current-password"
              autoFocus
            />
          </label>
          <label className="auth-field">
            <span>新密码</span>
            <input
              type="password"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
              placeholder="至少 6 位"
              autoComplete="new-password"
            />
          </label>
          <label className="auth-field">
            <span>确认新密码</span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </label>
          {error && <div className="auth-error">{error}</div>}
          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? '修改中…' : '修改密码'}
          </button>
          <div className="auth-links">
            <Link to="/account">返回账号</Link>
          </div>
        </form>
      )}
    </AuthPageShell>
  )
}
