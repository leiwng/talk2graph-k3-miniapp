import { Link } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { useAuthStore } from '../store/auth'

export function AccountPage() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  if (!user) return null

  return (
    <AuthPageShell>
      <h2 className="auth-title">账号</h2>
      <p className="auth-sub">{user.email}</p>

      <div className="account-info">
        <div className="account-row">
          <span className="account-label">用户名</span>
          <span className="account-value">{user.username}</span>
        </div>
        <div className="account-row">
          <span className="account-label">角色</span>
          <span className="account-value">
            {user.role === 'admin' ? '管理员' : '普通用户'}
          </span>
        </div>
        <div className="account-row">
          <span className="account-label">状态</span>
          <span className="account-value">
            {user.status === 'active' ? '正常' : '已禁用'}
          </span>
        </div>
        {user.last_login_at && (
          <div className="account-row">
            <span className="account-label">上次登录</span>
            <span className="account-value">
              {new Date(user.last_login_at).toLocaleString('zh-CN')}
            </span>
          </div>
        )}
        <div className="account-row">
          <span className="account-label">注册时间</span>
          <span className="account-value">
            {new Date(user.created_at).toLocaleString('zh-CN')}
          </span>
        </div>
      </div>

      <div className="account-actions">
        <Link to="/account/password" className="btn btn-ghost btn-block">修改密码</Link>
        <Link to="/app" className="btn btn-ghost btn-block">返回工作台</Link>
        <button
          className="btn btn-danger btn-block"
          onClick={() => void logout().then(() => window.location.href = '/')}
        >
          退出登录
        </button>
      </div>
    </AuthPageShell>
  )
}
