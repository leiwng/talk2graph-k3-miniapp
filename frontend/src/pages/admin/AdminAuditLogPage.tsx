import { useEffect, useState } from 'react'
import { authApi } from '../../api/auth'
import type { AuditLogItem } from '../../api/types'

export function AdminAuditLogPage() {
  const [items, setItems] = useState<AuditLogItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [actionFilter, setActionFilter] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 50

  const loadLogs = async () => {
    setLoading(true)
    try {
      const r = await authApi.listAuditLogs({
        action: actionFilter || undefined,
        limit: pageSize,
        offset: page * pageSize,
      })
      setItems(r.items)
      setTotal(r.total)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadLogs() }, [actionFilter, page])

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <h1>审计日志</h1>
        <span className="admin-total">共 {total} 条</span>
      </div>

      <div className="admin-filters">
        <select value={actionFilter} onChange={(e) => { setActionFilter(e.target.value); setPage(0) }}>
          <option value="">全部 action</option>
          <option value="auth.register.success">注册成功</option>
          <option value="auth.login.success">登录成功</option>
          <option value="auth.login.failed">登录失败</option>
          <option value="auth.logout">登出</option>
          <option value="auth.password.changed">改密</option>
          <option value="auth.password.reset">重置密码</option>
          <option value="chat.send">画图</option>
          <option value="session.delete">删会话</option>
          <option value="order.create">创建订单</option>
          <option value="order.paid">订单支付</option>
        </select>
      </div>

      {loading ? (
        <div className="admin-loading">加载中…</div>
      ) : items.length === 0 ? (
        <div className="admin-empty">暂无日志</div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>Action</th>
              <th>操作者</th>
              <th>对象</th>
              <th>IP</th>
              <th>元数据</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{new Date(item.created_at).toLocaleString()}</td>
                <td><code>{item.action}</code></td>
                <td>{item.actor_email || '-'}</td>
                <td>
                  {item.target_type && item.target_id
                    ? `${item.target_type}/${item.target_id.slice(0, 8)}`
                    : '-'}
                </td>
                <td>{item.ip_address || '-'}</td>
                <td>
                  {item.metadata
                    ? <code className="meta-cell">{JSON.stringify(item.metadata).slice(0, 100)}</code>
                    : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div className="admin-pagination">
          <button
            className="btn btn-ghost btn-sm"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            上一页
          </button>
          <span className="page-info">{page + 1} / {totalPages}</span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page >= totalPages - 1}
            onClick={() => setPage(page + 1)}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}
