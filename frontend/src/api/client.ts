import type {
  ChatResult,
  DSL,
  Message,
  PatchOp,
  ProviderInfo,
  SessionInfo,
  Solution,
} from './types'

const BASE = '/api'

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!r.ok) {
    let detail: any = ''
    try {
      const j = await r.json()
      detail = j.detail ?? j.error ?? j
    } catch {
      detail = await r.text()
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
