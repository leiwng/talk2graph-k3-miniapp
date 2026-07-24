import { useEffect, useState } from 'react'
import { adminApi } from '../../api/admin'
import type { AdminUser } from '../../api/types'

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 20

  // V3.5 批量操作 state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchOpen, setBatchOpen] = useState(false)
  const [batchAction, setBatchAction] = useState<'enable' | 'disable' | 'set_quota' | 'set_subscription'>('disable')
  const [batchQuota, setBatchQuota] = useState('')
  const [batchPlan, setBatchPlan] = useState('pro')
  const [batchSubmitting, setBatchSubmitting] = useState(false)
  const [batchResult, setBatchResult] = useState<string | null>(null)

  const loadUsers = async () => {
    setLoading(true)
    try {
      const r = await adminApi.listUsers({
        search: search || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
        limit: pageSize,
        offset: page * pageSize,
      })
      setUsers(r.items)
      setTotal(r.total)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadUsers() }, [page, roleFilter, statusFilter])

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(0)
    loadUsers()
  }

  const toggleStatus = async (u: AdminUser) => {
    const newStatus = u.status === 'disabled' ? 'active' : 'disabled'
    if (!confirm(`确定${newStatus === 'disabled' ? '禁用' : '启用'}用户 ${u.email}？`)) return
    try {
      await adminApi.updateUser(u.id, { status: newStatus })
      loadUsers()
    } catch (err: any) {
      alert(err.message || '操作失败')
    }
  }

  const toggleRole = async (u: AdminUser) => {
    const newRole = u.role === 'admin' ? 'user' : 'admin'
    if (!confirm(`确定把 ${u.email} 设为${newRole === 'admin' ? '管理员' : '普通用户'}？`)) return
    try {
      await adminApi.updateUser(u.id, { role: newRole })
      loadUsers()
    } catch (err: any) {
      alert(err.message || '操作失败')
    }
  }

  // V3.5 批量操作
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const toggleSelectAll = () => {
    if (selectedIds.size === users.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(users.map((u) => u.id)))
    }
  }
  const clearSelection = () => {
    setSelectedIds(new Set())
    setBatchResult(null)
  }

  const onBatchSubmit = async () => {
    if (selectedIds.size === 0) return
    setBatchSubmitting(true)
    setBatchResult(null)
    try {
      const ids = Array.from(selectedIds)
      const payload: any = {}
      if (batchAction === 'set_quota') {
        const v = batchQuota.trim()
        if (v === '') payload.daily_graph_limit_override = null
        else payload.daily_graph_limit_override = Number(v)
      } else if (batchAction === 'set_subscription') {
        payload.plan_code = batchPlan
        payload.period_days = batchPlan === 'pro' ? 30 : undefined
      }
      const r = await adminApi.batchUpdateUsers({
        user_ids: ids,
        action: batchAction,
        payload,
      })
      setBatchResult(r.message)
      // 清选区 + 重新加载
      setSelectedIds(new Set())
      loadUsers()
    } catch (err: any) {
      setBatchResult(err.message || '操作失败')
    } finally {
      setBatchSubmitting(false)
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <h1>用户管理</h1>
        <span className="admin-total">共 {total} 个用户</span>
      </div>

      <form className="admin-filters" onSubmit={onSearch}>
        <input
          type="text"
          placeholder="搜索 email / 用户名"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(0) }}>
          <option value="">全部角色</option>
          <option value="user">普通用户</option>
          <option value="admin">管理员</option>
        </select>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}>
          <option value="">全部状态</option>
          <option value="active">正常</option>
          <option value="pending_email_verification">待验证</option>
          <option value="disabled">已禁用</option>
        </select>
        <button type="submit" className="btn btn-primary">搜索</button>
      </form>

      {/* V3.5 批量操作工具栏 */}
      {selectedIds.size > 0 && (
        <div className="batch-toolbar">
          <span>已选 {selectedIds.size} 个用户</span>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => { setBatchOpen(true); setBatchResult(null) }}
          >
            批量操作 ▾
          </button>
          <button className="btn btn-ghost btn-sm" onClick={clearSelection}>
            取消选择
          </button>
        </div>
      )}

      {loading ? (
        <div className="admin-loading">加载中…</div>
      ) : users.length === 0 ? (
        <div className="admin-empty">暂无用户</div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th className="col-check">
                <input
                  type="checkbox"
                  checked={selectedIds.size === users.length && users.length > 0}
                  onChange={toggleSelectAll}
                />
              </th>
              <th>Email</th>
              <th>用户名</th>
              <th>角色</th>
              <th>状态</th>
              <th>邮箱</th>
              <th>最近登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className={selectedIds.has(u.id) ? 'row-selected' : ''}>
                <td className="col-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(u.id)}
                    onChange={() => toggleSelect(u.id)}
                  />
                </td>
                <td>{u.email}</td>
                <td>{u.username}</td>
                <td>
                  <span className={`badge ${u.role === 'admin' ? 'badge-admin' : ''}`}>
                    {u.role === 'admin' ? '管理员' : '用户'}
                  </span>
                </td>
                <td>
                  <span className={`badge badge-${u.status}`}>
                    {u.status === 'active' ? '正常' :
                     u.status === 'pending_email_verification' ? '待验证' :
                     u.status === 'disabled' ? '禁用' : u.status}
                  </span>
                </td>
                <td>{u.email_verified ? '✓' : '-'}</td>
                <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : '-'}</td>
                <td>
                  <div className="admin-row-actions">
                    <a href={`/admin/users/${u.id}`} className="btn btn-ghost btn-sm">详情</a>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => toggleRole(u)}
                    >
                      {u.role === 'admin' ? '降为用户' : '升为管理员'}
                    </button>
                    <button
                      className={`btn btn-sm ${u.status === 'disabled' ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => toggleStatus(u)}
                    >
                      {u.status === 'disabled' ? '启用' : '禁用'}
                    </button>
                  </div>
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

      {/* 批量操作弹窗 */}
      {batchOpen && (
        <div className="batch-modal-backdrop" onClick={() => setBatchOpen(false)}>
          <div className="batch-modal" onClick={(e) => e.stopPropagation()}>
            <div className="batch-modal-header">
              <h3>批量操作 {selectedIds.size} 个用户</h3>
              <button className="batch-close" onClick={() => setBatchOpen(false)}>×</button>
            </div>
            <div className="batch-modal-body">
              <label className="admin-field">
                <span>操作类型</span>
                <select
                  value={batchAction}
                  onChange={(e) => setBatchAction(e.target.value as any)}
                >
                  <option value="enable">启用账号</option>
                  <option value="disable">禁用账号</option>
                  <option value="set_quota">设置配额覆盖</option>
                  <option value="set_subscription">设置订阅</option>
                </select>
              </label>

              {batchAction === 'set_quota' && (
                <label className="admin-field">
                  <span>配额（空=默认 / 0=无限 / 正整数=N/天）</span>
                  <input
                    type="text"
                    value={batchQuota}
                    onChange={(e) => setBatchQuota(e.target.value)}
                    placeholder="留空用 plan 默认；或 0 / 正整数"
                  />
                </label>
              )}

              {batchAction === 'set_subscription' && (
                <label className="admin-field">
                  <span>套餐</span>
                  <select
                    value={batchPlan}
                    onChange={(e) => setBatchPlan(e.target.value)}
                  >
                    <option value="free">free（5/天）</option>
                    <option value="pro">pro（30/天，30 天）</option>
                    <option value="enterprise">enterprise（无限）</option>
                  </select>
                </label>
              )}

              <div className="batch-warning">
                ⚠️ 单次最多 100 个用户。不能在批量操作中禁用自己的账号。
              </div>

              {batchResult && (
                <div className={batchResult.includes('失败') ? 'admin-error' : 'admin-success'}>
                  {batchResult}
                </div>
              )}
            </div>
            <div className="batch-modal-footer">
              <button
                className="btn btn-ghost"
                onClick={() => setBatchOpen(false)}
                disabled={batchSubmitting}
              >
                取消
              </button>
              <button
                className="btn btn-primary"
                onClick={onBatchSubmit}
                disabled={batchSubmitting}
              >
                {batchSubmitting ? '处理中…' : `执行批量操作（${selectedIds.size} 个）`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
