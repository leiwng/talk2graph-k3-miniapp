import { useEffect } from 'react'
import { Canvas } from './components/Canvas'
import { ChatPanel } from './components/ChatPanel'
import { RightPanel } from './components/RightPanel'
import { TopBar } from './components/TopBar'
import { useStore } from './store'

export function App() {
  const init = useStore((s) => s.init)
  const loading = useStore((s) => s.loading)
  const activeTab = useStore((s) => s.activeTab)
  const setActiveTab = useStore((s) => s.setActiveTab)
  const debugUI = useStore((s) => s.debugUI)

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

  const tabClass = (tab: 'chat' | 'canvas' | 'objects') =>
    `panel-wrap panel-${tab} ${activeTab === tab ? 'tab-active' : ''}`

  return (
    <div className={`app ${debugUI ? 'debug-ui' : 'prod-ui'}`}>
      <TopBar />
      <div className="body">
        <div className={tabClass('chat')}>
          <ChatPanel />
        </div>
        <div className={tabClass('canvas')}>
          <Canvas />
        </div>
        {debugUI && (
          <div className={tabClass('objects')}>
            <RightPanel />
          </div>
        )}
      </div>
      <MobileTabBar activeTab={activeTab} onChange={setActiveTab} debugUI={debugUI} />
    </div>
  )
}

function MobileTabBar({
  activeTab,
  onChange,
  debugUI,
}: {
  activeTab: 'chat' | 'canvas' | 'objects'
  onChange: (t: 'chat' | 'canvas' | 'objects') => void
  debugUI: boolean
}) {
  const tabs: { id: 'chat' | 'canvas' | 'objects'; icon: string; label: string }[] = [
    { id: 'chat', icon: '💬', label: '对话' },
    { id: 'canvas', icon: '📊', label: '画板' },
    ...(debugUI ? [{ id: 'objects' as const, icon: '📐', label: '对象' }] : []),
  ]
  return (
    <div className="mobile-tab-bar">
      {tabs.map((t) => (
        <button
          key={t.id}
          className={activeTab === t.id ? 'active' : ''}
          onClick={() => onChange(t.id)}
        >
          <span className="tab-icon">{t.icon}</span>
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  )
}
