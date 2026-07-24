import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'

export function UserMenu() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!user) return null

  const initial = user.username.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()

  const onLogout = async () => {
    await logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="dropdown-wrap user-menu" ref={ref}>
      <button
        className="user-avatar-btn"
        onClick={() => setOpen((v) => !v)}
        title={user.email}
      >
        <span className="user-avatar">{initial}</span>
        <span className="user-name">{user.username}</span>
        <span className="caret">▾</span>
      </button>
      {open && (
        <div className="dropdown-menu user-menu-dropdown">
          <div className="user-menu-header">
            <div className="user-menu-email">{user.email}</div>
            <div className="user-menu-role">
              {user.role === 'admin' ? '管理员' : '普通用户'}
            </div>
          </div>
          <Link to="/account" onClick={() => setOpen(false)}>账号信息</Link>
          <Link to="/account/password" onClick={() => setOpen(false)}>修改密码</Link>
          {user.role === 'admin' && (
            <>
              <div className="dropdown-divider" />
              <Link to="/admin" onClick={() => setOpen(false)}>管理后台</Link>
            </>
          )}
          <div className="dropdown-divider" />
          <button onClick={onLogout}>退出登录</button>
        </div>
      )}
    </div>
  )
}
