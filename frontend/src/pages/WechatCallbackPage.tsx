import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { storeAuth } from '../api/auth'
import { useAuthStore } from '../store/auth'

export function WechatCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const errorParam = searchParams.get('error')
  const checkAuth = useAuthStore((s) => s.checkAuth)
  const [error, setError] = useState<string | null>(errorParam)

  useEffect(() => {
    if (!token) {
      setError('未收到登录凭证')
      return
    }
    // 用 token 调 /me 获取用户信息
    (async () => {
      try {
        // 直接存储 token，调 me 拿用户
        const r = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!r.ok) {
          setError('登录失败：' + r.status)
          return
        }
        const user = await r.json()
        storeAuth({ token, user })
        // 触发 authStore 检查（让 state 同步）
        await checkAuth()
        navigate('/app', { replace: true })
      } catch (e: any) {
        setError('登录失败：' + (e.message || ''))
      }
    })()
  }, [token, navigate, checkAuth])

  return (
    <AuthPageShell>
      <h2 className="auth-title">微信登录</h2>
      {error ? (
        <div className="auth-error">
          <p>登录失败：{error}</p>
          <p className="auth-hint" style={{ marginTop: 8 }}>
            <a href="/login">返回登录页</a>
          </p>
        </div>
      ) : (
        <div className="auth-info-text">
          <p>正在登录…</p>
        </div>
      )}
    </AuthPageShell>
  )
}
