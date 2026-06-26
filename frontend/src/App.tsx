import { useEffect } from 'react'
import { Canvas } from './components/Canvas'
import { ChatPanel } from './components/ChatPanel'
import { RightPanel } from './components/RightPanel'
import { TopBar } from './components/TopBar'
import { useStore } from './store'

export function App() {
  const init = useStore((s) => s.init)
  const loading = useStore((s) => s.loading)

  useEffect(() => {
    init()
  }, [init])

  if (loading) {
    return (
      <div
        style={{
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--muted)',
        }}
      >
        话图 T2G 启动中…
      </div>
    )
  }

  return (
    <div className="app">
      <TopBar />
      <div className="body">
        <ChatPanel />
        <Canvas />
        <RightPanel />
      </div>
    </div>
  )
}
