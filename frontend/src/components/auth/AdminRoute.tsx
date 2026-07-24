import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { authApi } from '../../api/auth'

export function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)
  const [checking, setChecking] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)
  const location = useLocation()

  useEffect(() => {
    if (isLoading) return
    if (!isAuthenticated) {
      setChecking(false)
      return
    }
    // 拉 /me 确认 role（user.role 可能在 register 时没拉到最新）
    (async () => {
      try {
        const u = await authApi.me()
        setIsAdmin(u.role === 'admin')
      } catch {
        setIsAdmin(false)
      } finally {
        setChecking(false)
      }
    })()
  }, [isAuthenticated, isLoading, location.pathname])

  if (isLoading || checking) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-card">
          <div className="auth-loading-spinner" />
          <span>正在验证权限…</span>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    const from = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?from=${from}`} replace />
  }

  if (!isAdmin) {
    return (
      <div className="admin-forbidden">
        <h2>403 - 无权访问</h2>
        <p>该页面仅管理员可访问。</p>
        <a href="/app" className="btn btn-primary">返回工作台</a>
      </div>
    )
  }

  return <>{children}</>
}
