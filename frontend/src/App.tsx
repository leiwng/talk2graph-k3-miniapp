import { useEffect } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Canvas } from './components/Canvas'
import { ChatPanel } from './components/ChatPanel'
import { RightPanel } from './components/RightPanel'
import { TopBar } from './components/TopBar'
import { AuthPageShell } from './components/auth/AuthPageShell'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { AccountPage } from './pages/AccountPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { PricingPage } from './pages/PricingPage'
import { SubscriptionPage } from './pages/SubscriptionPage'
import { useStore } from './store'
import { useAuthStore } from './store/auth'

export function App() {
  const initApp = useStore((s) => s.init)
  const initAuth = useAuthStore((s) => s.init)

  useEffect(() => {
    void initAuth().then(() => initApp())
  }, [initApp, initAuth])

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/pricing" element={<PricingPage />} />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account"
        element={
          <ProtectedRoute>
            <AccountPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/password"
        element={
          <ProtectedRoute>
            <ChangePasswordPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account/subscription"
        element={
          <ProtectedRoute>
            <SubscriptionPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function LandingPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)

  if (isLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-card">
          <div className="auth-loading-spinner" />
          <span>正在加载…</span>
        </div>
      </div>
    )
  }

  return (
    <AuthPageShell>
      <div className="landing-content">
        <h1 className="landing-title">用一句话，画出几何图形</h1>
        <p className="landing-sub">
          话图 T2G 帮 K12 数学老师用自然语言画图，给课件用。
        </p>
        <div className="landing-cta">
          {isAuthenticated ? (
            <>
              <a className="btn btn-primary" href="/app">进入工作台 →</a>
              <a className="btn btn-ghost" href="/pricing">查看价格</a>
            </>
          ) : (
            <>
              <a className="btn btn-primary" href="/register">免费注册</a>
              <a className="btn btn-ghost" href="/login">已注册，去登录</a>
              <a className="btn btn-ghost" href="/pricing">查看价格</a>
            </>
          )}
        </div>
        <ul className="landing-features">
          <li>✓ 自然语言作图（点 / 线 / 圆 / 多边形 / 函数曲线）</li>
          <li>✓ 几何约束求解（精度达机器精度）</li>
          <li>✓ 一键导出 SVG / PNG / PDF（PPT 友好）</li>
        </ul>
      </div>
    </AuthPageShell>
  )
}

function AppShell() {
  const activeTab = useStore((s) => s.activeTab)
  const setActiveTab = useStore((s) => s.setActiveTab)
  const debugUI = useStore((s) => s.debugUI)
  const sessionId = useStore((s) => s.sessionId)
  const newSession = useStore((s) => s.newSession)

  useEffect(() => {
    // V2-F.1：进入 /app 时若无 session 则自动创建
    if (!sessionId) {
      void newSession()
    }
  }, [sessionId, newSession])

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
