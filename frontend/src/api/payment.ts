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
    let detail: any = ''
    try {
      detail = (await r.json()).detail
    } catch {
      detail = await r.text()
    }
    throw new Error(typeof detail === 'string' ? detail : detail?.message || 'request failed')
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
