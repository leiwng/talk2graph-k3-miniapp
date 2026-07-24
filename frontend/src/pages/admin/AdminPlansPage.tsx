import { useEffect, useState } from 'react'
import { adminApi } from '../../api/admin'
import type { AdminPlan } from '../../api/types'

export function AdminPlansPage() {
  const [plans, setPlans] = useState<AdminPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Record<string, { name: string; price_cents: string; daily_graph_limit: string; description: string }>>({})
  const [info, setInfo] = useState<Record<string, string>>({})
  const [error, setError] = useState<Record<string, string>>({})

  const load = async () => {
    setLoading(true)
    try {
      const r = await adminApi.listPlans()
      setPlans(r.items)
      const edit: typeof editing = {}
      for (const p of r.items) {
        edit[p.code] = {
          name: p.name,
          price_cents: String(p.price_cents),
          daily_graph_limit: String(p.daily_graph_limit),
          description: p.description || '',
        }
      }
      setEditing(edit)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const onSave = async (code: string) => {
    const e = editing[code]
    if (!e) return
    setInfo({ ...info, [code]: '' })
    setError({ ...error, [code]: '' })
    try {
      await adminApi.updatePlan(code, {
        name: e.name,
        price_cents: Number(e.price_cents),
        daily_graph_limit: Number(e.daily_graph_limit),
        description: e.description,
      })
      setInfo({ ...info, [code]: '已保存' })
      load()
    } catch (err: any) {
      setError({ ...error, [code]: err.message || '保存失败' })
    }
  }

  if (loading) return <div className="admin-loading">加载中…</div>

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <h1>套餐管理</h1>
        <span className="admin-total">共 {plans.length} 个套餐</span>
      </div>

      <p className="admin-hint">
        改 daily_graph_limit 后所有该 plan 用户立即生效（不需要重启 backend）。
        价格单位是分（如 2900 = ¥29.00）。
      </p>

      <div className="plans-grid">
        {plans.map((p) => {
          const e = editing[p.code] || { name: '', price_cents: '', daily_graph_limit: '', description: '' }
          return (
            <div key={p.code} className="plan-card">
              <div className="plan-card-header">
                <h3>{p.code}</h3>
                <span className={`badge badge-${p.status}`}>{p.status}</span>
              </div>

              <label className="admin-field">
                <span>名称</span>
                <input
                  type="text"
                  value={e.name}
                  onChange={(ev) => setEditing({
                    ...editing,
                    [p.code]: { ...e, name: ev.target.value },
                  })}
                />
              </label>

              <label className="admin-field">
                <span>价格（分）</span>
                <input
                  type="number"
                  value={e.price_cents}
                  onChange={(ev) => setEditing({
                    ...editing,
                    [p.code]: { ...e, price_cents: ev.target.value },
                  })}
                />
              </label>

              <label className="admin-field">
                <span>每日画图配额</span>
                <input
                  type="number"
                  value={e.daily_graph_limit}
                  onChange={(ev) => setEditing({
                    ...editing,
                    [p.code]: { ...e, daily_graph_limit: ev.target.value },
                  })}
                />
                <small>0 = 无限</small>
              </label>

              <label className="admin-field">
                <span>描述</span>
                <textarea
                  rows={2}
                  value={e.description}
                  onChange={(ev) => setEditing({
                    ...editing,
                    [p.code]: { ...e, description: ev.target.value },
                  })}
                />
              </label>

              <div className="plan-card-actions">
                <button className="btn btn-primary btn-sm" onClick={() => onSave(p.code)}>
                  保存
                </button>
                {info[p.code] && <span className="admin-success-inline">{info[p.code]}</span>}
                {error[p.code] && <span className="admin-error-inline">{error[p.code]}</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
