import type {
  ChatResult,
  DSL,
  Message,
  PatchOp,
  ProviderInfo,
  SessionInfo,
  Solution,
} from './types'
import { authHeader, getStoredToken, clearStoredAuth } from './auth'

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
  if (r.status === 401) {
    // 仅当原本有 token 时才清，避免公开页 401 误清
    if (getStoredToken()) {
      clearStoredAuth()
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
    // 后端 friendly error 是对象 {code, message, hint, detail}
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

export const api = {
  // health
  health(): Promise<{ status: string; version: string; debug_ui?: boolean }> {
    return request('/health')
  },

  // session
  createSession(provider?: string): Promise<SessionInfo> {
    return request('/session', {
      method: 'POST',
      body: JSON.stringify({ llm_provider: provider ?? null }),
    })
  },
  getSession(sid: string): Promise<SessionInfo> {
    return request(`/session/${sid}`)
  },
  deleteSession(sid: string): Promise<{ deleted: string }> {
    return request(`/session/${sid}`, { method: 'DELETE' })
  },

  // dsl & history
  getCurrentDSL(sid: string): Promise<{
    seq: number
    dsl: DSL | null
    solution: Solution | null
  }> {
    return request(`/session/${sid}/dsl`)
  },
  getMessages(sid: string): Promise<Message[]> {
    return request(`/session/${sid}/messages`)
  },
  getHistory(sid: string): Promise<{ seqs: number[]; current: number }> {
    return request(`/session/${sid}/history`)
  },

  // chat
  chat(sid: string, nl: string, provider?: string): Promise<ChatResult> {
    return request(`/session/${sid}/chat`, {
      method: 'POST',
      body: JSON.stringify({ nl, provider: provider ?? null }),
    })
  },

  // chat SSE 流式：onStage 回调每阶段触发；onToken/onObjectSeen 在 LLM 阶段触发
  async chatStream(
    sid: string,
    nl: string,
    provider: string | null,
    onStage: (stage: string) => void,
    onToken?: (text: string) => void,
    onObjectSeen?: (id: string, kind: string) => void,
  ): Promise<ChatResult> {
    const r = await fetch(`${BASE}/session/${sid}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader(),
      },
      body: JSON.stringify({ nl, provider: provider ?? null }),
    })
    if (!r.ok || !r.body) {
      // 兜底：非流式错误，复用 request 的错误归一
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

    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let result: ChatResult | null = null

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      // SSE 帧以 \n\n 分隔
      let i: number
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, i)
        buf = buf.slice(i + 2)
        const evt = _parseSseFrame(frame)
        if (!evt) continue
        if (evt.event === 'stage') {
          onStage(evt.data.stage)
        } else if (evt.event === 'token') {
          onToken?.(evt.data.text)
        } else if (evt.event === 'object_seen') {
          onObjectSeen?.(evt.data.id, evt.data.kind)
        } else if (evt.event === 'done') {
          result = evt.data as ChatResult
        } else if (evt.event === 'error') {
          // error 事件 detail 字段
          const d = evt.data
          const msg = d.hint ? `${d.message}（${d.hint}）` : (d.message || 'stream error')
          const err = new Error(msg) as Error & { code?: string; detail?: string }
          err.code = d.code
          err.detail = d.detail
          throw err
        }
      }
    }

    if (result) return result
    throw new Error('stream ended without done event')
  },

  // direct patch (property panel)
  patch(sid: string, ops: PatchOp[]): Promise<{
    ok: boolean
    seq: number
    dsl: DSL
    solution: Solution
    svg: string
  }> {
    return request(`/session/${sid}/patch`, {
      method: 'POST',
      body: JSON.stringify({ ops }),
    })
  },

  // undo / redo
  undo(sid: string): Promise<{ seq: number; dsl: DSL | null; solution: Solution | null }> {
    return request(`/session/${sid}/undo`, { method: 'POST' })
  },
  redo(sid: string): Promise<{ seq: number; dsl: DSL | null; solution: Solution | null }> {
    return request(`/session/${sid}/redo`, { method: 'POST' })
  },

  // feedback
  sendFeedback(
    sid: string,
    rating: 'good' | 'bad',
    comment?: string,
  ): Promise<{ id: number; rating: string; created_at: string }> {
    return request(`/session/${sid}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ rating, comment: comment ?? null }),
    })
  },

  // providers
  listProviders(): Promise<{ providers: ProviderInfo[]; default: string }> {
    return request('/providers')
  },

  // export urls (browser navigates directly)
  exportUrl(sid: string, fmt: 'svg' | 'png' | 'pdf'): string {
    return `${BASE}/export/${sid}.${fmt}`
  },
}

// SSE 帧解析：返回 {event, data} 或 null（空帧）
function _parseSseFrame(frame: string): { event: string; data: any } | null {
  let event = ''
  let dataStr = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) dataStr += line.slice(6)
  }
  if (!event || !dataStr) return null
  try { return { event, data: JSON.parse(dataStr) } } catch { return null }
}
