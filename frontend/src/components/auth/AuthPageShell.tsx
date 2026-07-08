import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export function AuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-brand">
          <span className="auth-brand-logo">话</span>
          <div className="auth-brand-text">
            <span className="auth-brand-title">话图 T2G</span>
            <span className="auth-brand-sub">用一句话画几何</span>
          </div>
        </Link>
        {children}
      </div>
    </div>
  )
}
