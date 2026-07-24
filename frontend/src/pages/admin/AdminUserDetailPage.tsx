import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { adminApi } from '../../api/admin'
import type { AdminUserDetail } from '../../api/types'

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<AdminUserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [quotaInput, setQuotaInput] = useState('')
  const [info, setInfo] = useState<string | null>(null)
  const [selectedPlan, setSelectedPlan] = useState('pro')

  const load = async () => {
    if (!userId) return
    setLoading(true)
    setError(null)
    try {
      const d = await adminApi.getUser(userId)
      setDetail(d)
      setQuotaInput(
        d.subscription?.daily_graph_limit_override !== null
          ? String(d.subscription?.daily_graph_limit_override ?? '')
          : ''
      )
      if (d.subscription) setSelectedPlan(d.subscription.plan_code)
    } catch (err: any) {
      setError(err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [userId])

  const onSetQuota = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!userId) return
    setInfo(null)
    setError(null)
    const value = quotaInput.trim() === '' ? null : Number(quotaInput)
    if (value !== null && (Number.isNaN(value) || value < 0)) {
      setError('配额必须是空（用默认）/ 0（无限）/ 正整数')
      return
    }
    try {
      await adminApi.setQuotaOverride(userId, value)
      setInfo('配额已更新')
      load()
    } catch (err: any) {
      setError(err.message || '更新失败')
    }
  }

  const onSetSubscription = async () => {
    if (!userId) return
    if (!confirm(`确定把用户切换到 ${selectedPlan} 套餐？`)) return
    setInfo(null)
    setError(null)
    try {
      const periodDays = selectedPlan === 'pro' ? 30 : selectedPlan === 'enterprise' ? undefined : undefined
      await adminApi.setSubscription(userId, {
        plan_code: selectedPlan,
        status: 'active',
        period_days: periodDays,
      })
      setInfo('订阅已更新')
      load()
    } catch (err: any) {
      setError(err.message || '更新失败')
    }
  }

  if (loading) return <div className="admin-loading">加载中…</div>
  if (error && !detail) return <div className="admin-error">{error}</div>
  if (!detail) return <div className="admin-empty">用户不存在</div>

  const { user, sessions_count, snapshots_count, subscription } = detail

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <h1>用户详情</h1>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/admin/users')}>
          ← 返回列表
        </button>
      </div>

      <div className="admin-section">
        <h2 className="admin-section-title">基本信息</h2>
        <div className="admin-detail-grid">
          <div><span>Email</span>{user.email}</div>
          <div><span>用户名</span>{user.username}</div>
          <div><span>角色</span>{user.role}</div>
          <div><span>状态</span>{user.status}</div>
          <div><span>邮箱验证</span>{user.email_verified ? '✓' : '未验证'}</div>
          <div><span>微信昵称</span>{user.wechat_nickname || '-'}</div>
          <div><span>注册时间</span>{new Date(user.created_at).toLocaleString()}</div>
          <div><span>最近登录</span>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : '-'}</div>
        </div>
      </div>

      <div className="admin-section">
        <h2 className="admin-section-title">使用情况</h2>
        <div className="admin-detail-grid">
          <div><span>会话数</span>{sessions_count}</div>
          <div><span>历史画图数</span>{snapshots_count}</div>
          <div>
            <span>当前订阅</span>
            {subscription ? `${subscription.plan_code}（${subscription.status}）` : 'free（无订阅记录）'}
          </div>
          <div>
            <span>配额覆盖</span>
            {subscription?.daily_graph_limit_override === null
              ? '未覆盖（用 plan 默认）'
              : subscription?.daily_graph_limit_override === 0
              ? '0（无限）'
              : `${subscription?.daily_graph_limit_override}/天`}
          </div>
        </div>
      </div>

      <div className="admin-section">
        <h2 className="admin-section-title">配额覆盖</h2>
        <p className="admin-hint">
          空 = 用 plan 默认配额；0 = 无限；正整数 = 每日 N 张图。改后立即生效。
        </p>
        <form className="admin-form-inline" onSubmit={onSetQuota}>
          <input
            type="text"
            value={quotaInput}
            onChange={(e) => setQuotaInput(e.target.value)}
            placeholder="空 / 0 / 正整数"
          />
          <button type="submit" className="btn btn-primary">保存配额</button>
        </form>
      </div>

      <div className="admin-section">
        <h2 className="admin-section-title">订阅管理</h2>
        <p className="admin-hint">
          直接给用户切换套餐（不走支付流程）。pro=30 天，enterprise=无限期。
        </p>
        <div className="admin-form-inline">
          <select value={selectedPlan} onChange={(e) => setSelectedPlan(e.target.value)}>
            <option value="free">free（5/天）</option>
            <option value="pro">pro（30/天，30 天）</option>
            <option value="enterprise">enterprise（无限）</option>
          </select>
          <button className="btn btn-primary" onClick={onSetSubscription}>应用</button>
        </div>
      </div>

      {info && <div className="admin-success">{info}</div>}
      {error && <div className="admin-error">{error}</div>}
    </div>
  )
}
