import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPageShell } from '../components/auth/AuthPageShell'
import { paymentApi } from '../api/payment'
import { useAuthStore } from '../store/auth'
import type { Plan } from '../api/types'

export function PricingPage() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    paymentApi.listPlans().then((data) => {
      setPlans(data.items)
      setLoading(false)
    }).catch(() => {
      setLoading(false)
      setError('加载套餐失败')
    })
  }, [])

  const onUpgrade = async (planCode: string) => {
    if (planCode === 'free') return
    if (planCode === 'enterprise') {
      window.location.href = 'mailto:support@yinhour.com?subject=企业版咨询'
      return
    }
    if (!isAuthenticated) {
      navigate('/login?from=/pricing')
      return
    }
    setCreating(planCode)
    setError(null)
    try {
      const resp = await paymentApi.createOrder(planCode)
      // 跳转到支付宝
      window.location.href = resp.pay_url
    } catch (e: any) {
      setError(e.message || '创建订单失败')
    } finally {
      setCreating(null)
    }
  }

  if (loading) {
    return (
      <AuthPageShell>
        <div style={{ textAlign: 'center', color: 'var(--muted)' }}>加载中…</div>
      </AuthPageShell>
    )
  }

  return (
    <div className="pricing-page">
      <div className="pricing-header">
        <h1 className="landing-title">选择套餐</h1>
        <p className="landing-sub">免费试用，按需升级</p>
      </div>

      <div className="pricing-cards">
        {plans.map((plan) => (
          <div key={plan.code} className={`pricing-card ${plan.code === 'pro' ? 'recommended' : ''}`}>
            {plan.code === 'pro' && <div className="pricing-badge">推荐</div>}
            <h2 className="pricing-name">{plan.name}</h2>
            <div className="pricing-price">
              {plan.price_cents === 0 ? (
                plan.code === 'enterprise' ? '联系我们' : '免费'
              ) : (
                <>
                  <span className="pricing-amount">¥{plan.price_cents / 100}</span>
                  <span className="pricing-period">/月</span>
                </>
              )}
            </div>
            <p className="pricing-desc">{plan.description}</p>
            <ul className="pricing-features">
              {plan.feature_bullets.map((b, i) => (
                <li key={i}>✓ {b}</li>
              ))}
            </ul>
            <button
              className={`btn ${plan.code === 'pro' ? 'btn-primary' : 'btn-ghost'} btn-block`}
              onClick={() => onUpgrade(plan.code)}
              disabled={creating === plan.code}
            >
              {creating === plan.code
                ? '跳转中…'
                : plan.code === 'free'
                ? '当前套餐'
                : plan.code === 'enterprise'
                ? '联系销售'
                : isAuthenticated
                ? '升级'
                : '注册并升级'}
            </button>
          </div>
        ))}
      </div>

      {error && <div className="auth-error" style={{ maxWidth: 600, margin: '20px auto' }}>{error}</div>}

      <div style={{ textAlign: 'center', marginTop: 40 }}>
        <Link to="/" className="btn btn-ghost">返回首页</Link>
      </div>
    </div>
  )
}
