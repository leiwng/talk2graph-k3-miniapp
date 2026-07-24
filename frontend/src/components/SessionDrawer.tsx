import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'

function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Math.max(0, now - then)
  const min = Math.floor(diff / 60_000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day} 天前`
  const dt = new Date(iso)
  return `${dt.getMonth() + 1}/${dt.getDate()}`
}

export function SessionDrawer() {
  const open = useStore((s) => s.drawerOpen)
  const setOpen = useStore((s) => s.setDrawerOpen)
  const sessions = useStore((s) => s.sessions)
  const sessionId = useStore((s) => s.sessionId)
  const switchSession = useStore((s) => s.switchSession)
  const deleteSession = useStore((s) => s.deleteSession)
  const renameSession = useStore((s) => s.renameSession)
  const newSession = useStore((s) => s.newSession)
  const busy = useStore((s) => s.busy)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const editInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingId])

  // ESC 关闭抽屉
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setOpen])

  const startEdit = (id: string, currentTitle: string) => {
    setEditingId(id)
    setEditValue(currentTitle || '')
  }
  const commitEdit = async () => {
    if (!editingId) return
    const sid = editingId
    const newTitle = editValue.trim()
    if (newTitle) {
      try {
        await renameSession(sid, newTitle)
      } catch {
        /* 失败保留原值 */
      }
    }
    setEditingId(null)
    setEditValue('')
  }
  const cancelEdit = () => {
    setEditingId(null)
    setEditValue('')
  }

  const onClickItem = async (sid: string) => {
    if (sid === sessionId || busy) return
    await switchSession(sid)
  }

  const onClickDelete = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    if (!confirm('确定删除此会话？删除后无法恢复。')) return
    await deleteSession(sid)
  }

  if (!open) return null

  return (
    <>
      <div className="drawer-backdrop" onClick={() => setOpen(false)} />
      <aside className="session-drawer" aria-label="历史会话">
        <div className="drawer-header">
          <h3>历史会话</h3>
          <button
            className="drawer-new-btn"
            onClick={() => {
              setOpen(false)
              void newSession()
            }}
            disabled={busy}
            title="新建会话"
          >
            + 新建
          </button>
        </div>

        <div className="drawer-body">
          {sessions.length === 0 && (
            <div className="drawer-empty">
              <p>暂无会话</p>
              <p className="drawer-empty-sub">点击右上「+ 新建」开始作图</p>
            </div>
          )}

          {sessions.map((s) => {
            const isActive = s.id === sessionId
            const isEditing = editingId === s.id
            return (
              <div
                key={s.id}
                className={`session-item ${isActive ? 'active' : ''}`}
                onClick={() => onClickItem(s.id)}
                title={s.title || '（未命名）'}
              >
                {isEditing ? (
                  <input
                    ref={editInputRef}
                    className="session-edit-input"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onBlur={commitEdit}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void commitEdit()
                      else if (e.key === 'Escape') cancelEdit()
                    }}
                    maxLength={200}
                    placeholder="输入会话标题"
                  />
                ) : (
                  <>
                    <div className="session-item-main">
                      <div className="session-title">
                        {s.title || '（未命名）'}
                      </div>
                      {s.last_user_nl && (
                        <div className="session-sub">
                          {s.last_user_nl}
                        </div>
                      )}
                      <div className="session-meta">
                        <span>{formatRelativeTime(s.updated_at)}</span>
                        {typeof s.message_count === 'number' && s.message_count > 0 && (
                          <>
                            <span className="dot">·</span>
                            <span>{s.message_count} 条消息</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="session-item-actions">
                      <button
                        className="icon-btn"
                        title="重命名"
                        onClick={(e) => {
                          e.stopPropagation()
                          startEdit(s.id, s.title || '')
                        }}
                      >
                        ✏
                      </button>
                      <button
                        className="icon-btn danger"
                        title="删除"
                        onClick={(e) => onClickDelete(e, s.id)}
                      >
                        ✕
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })}
        </div>

        <div className="drawer-footer">
          <button className="drawer-close-btn" onClick={() => setOpen(false)}>
            关闭
          </button>
        </div>
      </aside>
    </>
  )
}
