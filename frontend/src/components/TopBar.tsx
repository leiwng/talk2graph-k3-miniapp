import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '../store'
import { api } from '../api/client'
import { authHeader } from '../api/auth'
import { ProviderSwitch } from './ProviderSwitch'
import { UserMenu } from './auth/UserMenu'

export const EXAMPLES: { icon: string; title: string; desc: string; nl: string }[] = [
  {
    icon: '△',
    title: '等边三角形',
    desc: '边长为 4 的正三角形',
    nl: '画一个等边三角形 ABC，边长为 4',
  },
  {
    icon: '∟',
    title: '直角三角形',
    desc: '直角边 3 和 4，含直角标记',
    nl: '画一个直角三角形 ABC，C 为直角顶点，BC=3，CA=4',
  },
  {
    icon: '□',
    title: '正方形',
    desc: '边长 5，标注所有顶点',
    nl: '画一个边长为 5 的正方形 ABCD',
  },
  {
    icon: '○',
    title: '圆与圆心角',
    desc: '半径 5，圆心角 90°',
    nl: '画圆 O，半径为 5，A、B 两点在圆上，∠AOB=90°',
  },
  {
    icon: '△',
    title: '等腰 + 内切圆',
    desc: '内切圆半径为 3',
    nl: '画一个内切圆半径为 3 的等腰三角形',
  },
]

export function TopBar() {
  const sessionId = useStore((s) => s.sessionId)
  const seq = useStore((s) => s.seq)
  const busy = useStore((s) => s.busy)
  const newSession = useStore((s) => s.newSession)
  const undo = useStore((s) => s.undo)
  const redo = useStore((s) => s.redo)
  const setDrawerOpen = useStore((s) => s.setDrawerOpen)
  const sessionsCount = useStore((s) => s.sessions.length)
  const [exportOpen, setExportOpen] = useState(false)

  const canExport = !!sessionId && seq > 0
  const canUndo = !!sessionId && seq > 0

  return (
    <div className="topbar">
      <button
        className="drawer-toggle-btn"
        onClick={() => setDrawerOpen(true)}
        title="历史会话"
        aria-label="打开历史会话"
      >
        <span className="hamburger" />
        <span className="hamburger" />
        <span className="hamburger" />
        {sessionsCount > 0 && (
          <span className="drawer-badge">{sessionsCount}</span>
        )}
      </button>

      <Link to="/" className="brand">
        <span className="logo">话</span>
        <span className="name">话图 T2G</span>
        <span className="sub">用一句话画几何</span>
      </Link>

      <button onClick={() => newSession()} disabled={busy} title="新建会话">
        + 新会话
      </button>
      <button onClick={() => undo()} disabled={!canUndo || busy} title="撤销">
        ← 撤销
      </button>
      <button onClick={() => redo()} disabled={!sessionId || busy} title="重做">
        重做 →
      </button>

      <div className="spacer" />

      <span className="seq-info" style={{ fontSize: 11, color: 'var(--muted)' }}>
        seq #{seq}
      </span>

      <ProviderSwitch />

      <div className="dropdown-wrap">
        <button onClick={() => setExportOpen((v) => !v)} disabled={!canExport}>
          导出 ▾
        </button>
        {exportOpen && (
          <div
            className="dropdown-menu"
            onMouseLeave={() => setExportOpen(false)}
          >
            {(['svg', 'png', 'pdf'] as const).map((fmt) => (
              <button
                key={fmt}
                onClick={async () => {
                  if (!sessionId) return
                  setExportOpen(false)
                  try {
                    const url = api.exportUrl(sessionId, fmt)
                    const r = await fetch(url, {
                      headers: authHeader(),
                    })
                    if (!r.ok) throw new Error(`导出失败：${r.status}`)
                    const blob = await r.blob()
                    const objUrl = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = objUrl
                    a.download = `${sessionId}.${fmt}`
                    document.body.appendChild(a)
                    a.click()
                    document.body.removeChild(a)
                    URL.revokeObjectURL(objUrl)
                  } catch (e: any) {
                    alert(e.message || '导出失败')
                  }
                }}
              >
                导出 {fmt.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      <UserMenu />
    </div>
  )
}
