import { useEffect, useState } from 'react'
import { adminApi } from '../../api/admin'

type FeedbackItem = {
  id: number
  session_id: string
  snapshot_seq: number | null
  rating: string
  comment: string | null
  nl: string | null
  llm_provider: string | null
  created_at: string
}

export function AdminFeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([])
  const [total, setTotal] = useState(0)
  const [good, setGood] = useState(0)
  const [bad, setBad] = useState(0)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    (async () => {
      setLoading(true)
      try {
        const r = await adminApi.listFeedback(days)
        setItems(r.items as FeedbackItem[])
        setTotal(r.total)
        setGood(r.good)
        setBad(r.bad)
      } catch {
        /* ignore */
      } finally {
        setLoading(false)
      }
    })()
  }, [days])

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <h1>反馈看板</h1>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>近 7 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">总反馈</div>
          <div className="stat-value">{total}</div>
        </div>
        <div className="stat-card stat-good">
          <div className="stat-label">👍 好</div>
          <div className="stat-value">{good}</div>
        </div>
        <div className="stat-card stat-bad">
          <div className="stat-label">👎 差</div>
          <div className="stat-value">{bad}</div>
        </div>
      </div>

      {loading ? (
        <div className="admin-loading">加载中…</div>
      ) : items.length === 0 ? (
        <div className="admin-empty">暂无反馈</div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>评级</th>
              <th>用户输入</th>
              <th>评论</th>
              <th>Provider</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((f) => (
              <tr key={f.id}>
                <td>{f.rating === 'good' ? '👍' : '👎'}</td>
                <td className="truncate-cell" title={f.nl || ''}>{f.nl || '-'}</td>
                <td className="truncate-cell" title={f.comment || ''}>{f.comment || '-'}</td>
                <td>{f.llm_provider || '-'}</td>
                <td>{new Date(f.created_at).toLocaleString()}</td>
                <td>
                  <a
                    href={`/api/admin/feedback.jsonl?days=${days}`}
                    className="btn btn-ghost btn-sm"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    导出全部
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
