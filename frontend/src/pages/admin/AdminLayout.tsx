import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/admin', label: '概览', icon: '📊', end: true },
  { to: '/admin/users', label: '用户', icon: '👥' },
  { to: '/admin/feedback', label: '反馈', icon: '💬' },
  { to: '/admin/audit', label: '审计日志', icon: '📋' },
  { to: '/admin/plans', label: '套餐', icon: '💰' },
]

export function AdminLayout() {
  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <div className="admin-brand">
          <span className="logo">话</span>
          <div>
            <div className="admin-brand-title">话图 Admin</div>
            <div className="admin-brand-sub">管理后台</div>
          </div>
        </div>
        <nav className="admin-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `admin-nav-item ${isActive ? 'active' : ''}`
              }
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="admin-sidebar-footer">
          <a href="/app" className="admin-nav-item">
            <span className="nav-icon">←</span>
            <span>返回工作台</span>
          </a>
        </div>
      </aside>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  )
}
