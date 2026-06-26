import { useState } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { ProviderSwitch } from './ProviderSwitch'

const EXAMPLES = [
  '画一个内切圆半径为 3 的等腰三角形',
  '画一个等边三角形 ABC，边长为 4',
  '画一个直角三角形 ABC，C 为直角顶点，BC=3，CA=4',
  '画一个边长为 5 的正方形 ABCD',
  '画圆 O，半径为 5，A、B 两点在圆上，AOB 角为 90 度',
]

export function TopBar() {
  const sessionId = useStore((s) => s.sessionId)
  const seq = useStore((s) => s.seq)
  const busy = useStore((s) => s.busy)
  const newSession = useStore((s) => s.newSession)
  const undo = useStore((s) => s.undo)
  const redo = useStore((s) => s.redo)
  const [exportOpen, setExportOpen] = useState(false)

  const canExport = !!sessionId && seq > 0
  const canUndo = !!sessionId && seq > 0

  return (
    <div className="topbar">
      <div className="brand">
        话图 T2G<span className="sub">用一句话画几何</span>
      </div>

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

      <span style={{ fontSize: 11, color: 'var(--muted)' }}>
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
                onClick={() => {
                  if (!sessionId) return
                  window.open(api.exportUrl(sessionId, fmt), '_blank')
                  setExportOpen(false)
                }}
              >
                导出 {fmt.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ProviderSwitchWrap() {
  return <ProviderSwitch />
}

export function ExampleHints({ onClick }: { onClick: (text: string) => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 11, color: 'var(--muted)' }}>试试：</div>
      {EXAMPLES.map((ex) => (
        <button
          key={ex}
          onClick={() => onClick(ex)}
          style={{ textAlign: 'left', fontSize: 12, padding: '4px 8px' }}
        >
          {ex}
        </button>
      ))}
    </div>
  )
}
