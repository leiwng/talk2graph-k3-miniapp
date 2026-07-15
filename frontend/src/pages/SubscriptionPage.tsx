import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { paymentApi } from '../api/payment'
import type { Subscription as SubType } from '../api/types'

export function SubscriptionPage() {
  const [sub, setSub] = useState<SubType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      const data = await paymentApi.getSubscription()
      setSub(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  if (loading) {
    return (
      <AuthPageShell>
        <div style={{ textAlign: 'center', color: 'var(--muted)' }}>加载中…</div>
      </AuthPageShell>
    )
  }

  if (error) {
    return (
      <AuthPageShell>
        <div className="auth-error">{error}</div>
      </AuthPageShell>
    )
  }

  if (!sub) return null

  const ent = sub.entitlement
  const isPro = ent.plan_code === 'pro'
  const isEnterprise = ent.plan_code === 'enterprise'

  return (
    <AuthPageShell>
      <h2 className="auth-title">我的订阅</h2>
      <p className="auth-sub">{ent.plan_name} · {ent.status === 'active' ? '生效中' : '免费'}</p>

      <div className="account-info">
        <div className="account-row">
          <span className="account-label">套餐</span>
          <span className="account-value">{sub.plan.name}</span>
        </div>
        <div className="account-row">
          <span className="account-label">状态</span>
          <span className="account-value">
            {ent.status === 'active' ? '✓ 生效中' : ent.status === 'expired' ? '已过期' : '免费版'}
          </span>
        </div>
        <div className="account-row">
          <span className="account-label">今日用量</span>
          <span className="account-value">
            {ent.daily_limit === 0
              ? `${ent.used_today} 张（无限）`
              : `${ent.used_today} / ${ent.daily_limit} 张`}
          </span>
        </div>
        <div className="account-row">
          <span className="account-label">剩余</span>
          <span className="account-value">
            {ent.daily_limit === 0 ? '无限' : `${Math.max(0, ent.remaining)} 张`}
          </span>
        </div>
        {sub.current_period_end && (
          <div className="account-row">
            <span className="account-label">到期时间</span>
            <span className="account-value">
              {new Date(sub.current_period_end).toLocaleDateString('zh-CN')}
            </span>
          </div>
        )}
      </div>

      {!isPro && !isEnterprise && (
        <div className="account-actions">
          <Link to="/pricing" className="btn btn-primary btn-block">升级到月度会员</Link>
        </div>
      )}

      <div className="account-actions" style={{ marginTop: 12 }}>
        <Link to="/account" className="btn btn-ghost btn-block">返回账号</Link>
        <Link to="/app" className="btn btn-ghost btn-block">返回工作台</Link>
      </div>
    </AuthPageShell>
  )
}
