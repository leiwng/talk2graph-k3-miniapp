import type { AuditLogListResp, AuthResp, User } from './types'

const BASE = '/api'

// ===================== Token 持久化 =====================

const LS_KEY = 't2g.auth'

export function loadStoredAuth(): { token: string; user: User } | null {
  const raw = localStorage.getItem(LS_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (parsed?.token && parsed?.user) return parsed
  } catch {
    // ignore
  }
  return null
}

export function storeAuth(auth: { token: string; user: User }): void {
  localStorage.setItem(LS_KEY, JSON.stringify(auth))
}

export function clearStoredAuth(): void {
  localStorage.removeItem(LS_KEY)
}

export function getStoredToken(): string | null {
  return loadStoredAuth()?.token ?? null
}

export function authHeader(): Record<string, string> {
  const token = getStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ===================== API =====================

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
      ...(options.headers || {}),
    },
    ...options,
  })
  if (r.status === 401) {
    // 仅当原本有 token 时才清，避免公开页 401 误清
    if (getStoredToken()) {
      clearStoredAuth()
      // 跳登录页（保留 from 参数）
      const from = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.href = `/login?from=${from}`
    }
    throw new Error('请先登录')
  }
  if (!r.ok) {
    // 只读一次 body（避免 "body stream already read" 错误）
    const bodyText = await r.text()
    let detail: any = bodyText
    try {
      const parsed = JSON.parse(bodyText)
      detail = parsed.detail ?? parsed.error ?? parsed
    } catch {
      // body 不是 JSON，保持 detail = bodyText
    }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const msg = detail.hint ? `${detail.message}（${detail.hint}）` : detail.message
      const err = new Error(msg) as Error & { code?: string; detail?: string }
      err.code = detail.code
      err.detail = detail.detail
      throw err
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return r.json() as Promise<T>
}

export const authApi = {
  register(email: string, password: string, username: string): Promise<AuthResp> {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, username }),
    })
  },

  login(email: string, password: string): Promise<AuthResp> {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  logout(): Promise<{ message: string }> {
    return request('/auth/logout', { method: 'POST' })
  },

  me(): Promise<User> {
    return request('/auth/me')
  },

  refresh(): Promise<AuthResp> {
    return request('/auth/refresh', { method: 'POST' })
  },

  changePassword(oldPassword: string, newPassword: string): Promise<{ message: string }> {
    return request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    })
  },

  // admin: 审计日志
  listAuditLogs(params?: {
    actor_id?: string
    action?: string
    target_type?: string
    target_id?: string
    start?: string
    end?: string
    limit?: number
    offset?: number
  }): Promise<AuditLogListResp> {
    const qs = new URLSearchParams()
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
      }
    }
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return request(`/audit-log${suffix}`)
  },
}
