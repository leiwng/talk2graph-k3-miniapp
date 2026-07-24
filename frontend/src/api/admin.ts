import type {
  AdminPlan,
  AdminStats,
  AdminUser,
  AdminUserDetail,
  AdminUserListResp,
} from './types'
import { authHeader } from './auth'

const BASE = '/api'

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!r.ok) {
    const bodyText = await r.text()
    let detail: any = bodyText
    try {
      const parsed = JSON.parse(bodyText)
      detail = parsed.detail ?? parsed.error ?? parsed
    } catch {
      // body 不是 JSON
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
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

export const adminApi = {
  // 统计
  stats(days: number = 7): Promise<AdminStats> {
    return request(`/admin/stats?days=${days}`)
  },

  // 反馈
  listFeedback(days: number = 30): Promise<{
    since: string
    total: number
    good: number
    bad: number
    items: Array<{
      id: number
      session_id: string
      snapshot_seq: number | null
      rating: string
      comment: string | null
      nl: string | null
      llm_provider: string | null
      created_at: string
    }>
  }> {
    return request(`/admin/feedback?days=${days}`)
  },

  // 用户
  listUsers(params?: {
    search?: string
    role?: string
    status?: string
    limit?: number
    offset?: number
  }): Promise<AdminUserListResp> {
    const qs = new URLSearchParams()
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
      }
    }
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return request(`/admin/users${suffix}`)
  },

  getUser(userId: string): Promise<AdminUserDetail> {
    return request(`/admin/users/${userId}`)
  },

  updateUser(userId: string, data: {
    role?: 'user' | 'admin'
    status?: 'active' | 'disabled' | 'pending_email_verification'
  }): Promise<AdminUserDetail> {
    return request(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  setQuotaOverride(userId: string, dailyGraphLimitOverride: number | null): Promise<{
    user_id: string
    daily_graph_limit_override: number | null
    message: string
  }> {
    return request(`/admin/users/${userId}/quota`, {
      method: 'PUT',
      body: JSON.stringify({ daily_graph_limit_override: dailyGraphLimitOverride }),
    })
  },

  setSubscription(userId: string, data: {
    plan_code: string
    status?: string
    period_days?: number
  }): Promise<{
    user_id: string
    plan_code: string
    status: string
    current_period_end: string | null
    message: string
  }> {
    return request(`/admin/users/${userId}/subscription`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  // 套餐
  listPlans(): Promise<{ items: AdminPlan[] }> {
    return request('/admin/plans')
  },

  updatePlan(code: string, data: {
    name?: string
    description?: string
    price_cents?: number
    daily_graph_limit?: number
    status?: string
    sort_order?: number
  }): Promise<AdminPlan> {
    return request(`/admin/plans/${code}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  // V3.5 批量操作
  batchUpdateUsers(data: {
    user_ids: string[]
    action: 'enable' | 'disable' | 'set_quota' | 'set_subscription'
    payload?: {
      daily_graph_limit_override?: number | null
      plan_code?: string
      period_days?: number
      status?: string
    }
  }): Promise<{
    action: string
    affected: number
    skipped: number
    message: string
  }> {
    return request('/admin/users/batch', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
}
