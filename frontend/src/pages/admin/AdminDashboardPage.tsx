import { useEffect, useState } from 'react'
import { adminApi } from '../../api/admin'
import type { AdminStats } from '../../api/types'

export function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)

  useEffect(() => {
    (async () => {
      setLoading(true)
      try {
        const s = await adminApi.stats(days)
        setStats(s)
      } catch {
        /* ignore */
      } finally {
        setLoading(false)
      }
    })()
  }, [days])

  if (loading) return <div className="admin-loading">加载中…</div>
  if (!stats) return <div className="admin-loading">暂无数据</div>

  const cards = [
    { label: '总用户数', value: stats.users, sub: `${stats.verified_users} 已验证邮箱` },
    { label: '近 N 天会话', value: stats.sessions, sub: `N=${days}` },
    { label: '近 N 天消息', value: stats.messages, sub: `N=${days}` },
    { label: '近 N 天画图', value: stats.snapshots, sub: `N=${days}` },
  ]

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <h1>概览</h1>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={1}>近 1 天</option>
          <option value={7}>近 7 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      </div>

      <div className="stats-grid">
        {cards.map((c) => (
          <div key={c.label} className="stat-card">
            <div className="stat-label">{c.label}</div>
            <div className="stat-value">{c.value}</div>
            <div className="stat-sub">{c.sub}</div>
          </div>
        ))}
      </div>

      <h2 className="admin-section-title">LLM Provider 用量</h2>
      {stats.providers.length === 0 ? (
        <p className="admin-empty">暂无 LLM 调用</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>调用次数</th>
              <th>输入 tokens</th>
              <th>输出 tokens</th>
              <th>平均延迟 (ms)</th>
            </tr>
          </thead>
          <tbody>
            {stats.providers.map((p) => (
              <tr key={p.provider}>
                <td>{p.provider}</td>
                <td>{p.calls}</td>
                <td>{p.tokens_in}</td>
                <td>{p.tokens_out}</td>
                <td>{Math.round(p.avg_latency_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
