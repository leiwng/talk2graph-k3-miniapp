import type { CreateOrderResp, Order, Plan, Subscription } from './types'
import { authHeader } from './auth'

const BASE = '/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
      ...(options.headers || {}),
    },
    ...options,
  })
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
    throw new Error(typeof detail === 'string' ? detail : 'request failed')
  }
  return r.json() as Promise<T>
}

export const paymentApi = {
  listPlans(): Promise<{ items: Plan[] }> {
    return fetch(`${BASE}/payment/plans`).then((r) => r.json())
  },

  getSubscription(): Promise<Subscription> {
    return request('/payment/subscription')
  },

  createOrder(planCode: string): Promise<CreateOrderResp> {
    return request('/payment/orders', {
      method: 'POST',
      body: JSON.stringify({ plan_code: planCode }),
    })
  },

  getOrder(orderId: string): Promise<Order> {
    return request(`/payment/orders/${orderId}`)
  },

  closeOrder(orderId: string): Promise<Order> {
    return request(`/payment/orders/${orderId}/close`, { method: 'POST' })
  },
}
