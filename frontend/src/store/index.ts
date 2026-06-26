import { create } from 'zustand'
import { api } from '../api/client'
import type { DSL, Message, PatchOp, Solution } from '../api/types'

const LS = {
  currentSessionId: 't2g.current_session_id',
  providerName: 't2g.provider',
  sessionsCache: 't2g.sessions',
}

interface SessionsCacheItem {
  id: string
  title: string | null
  updated_at: string
}

export interface AppState {
  sessionId: string | null
  sessions: SessionsCacheItem[]
  providerName: string
  availableProviders: { name: string; model: string; enabled: boolean }[]
  defaultProvider: string

  dsl: DSL | null
  solution: Solution | null
  svg: string | null
  seq: number
  selectedObjectId: string | null

  messages: Message[]

  loading: boolean
  busy: boolean
  errorBanner: string | null

  // actions
  init: () => Promise<void>
  newSession: () => Promise<void>
  switchSession: (sid: string) => Promise<void>
  deleteSession: (sid: string) => Promise<void>
  sendChat: (nl: string) => Promise<void>
  applyPatch: (ops: PatchOp[]) => Promise<void>
  undo: () => Promise<void>
  redo: () => Promise<void>
  selectObject: (id: string | null) => void
  setProvider: (name: string) => void
  dismissError: () => void
  sendFeedback: (rating: 'good' | 'bad', comment?: string) => Promise<void>
}

function readJSON<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v ? (JSON.parse(v) as T) : fallback
  } catch {
    return fallback
  }
}

function writeJSON(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}

export const useStore = create<AppState>((set, get) => ({
  sessionId: null,
  sessions: readJSON<SessionsCacheItem[]>(LS.sessionsCache, []),
  providerName: localStorage.getItem(LS.providerName) || 'zhipu',
  availableProviders: [],
  defaultProvider: 'zhipu',

  dsl: null,
  solution: null,
  svg: null,
  seq: 0,
  selectedObjectId: null,

  messages: [],

  loading: true,
  busy: false,
  errorBanner: null,

  async init() {
    set({ loading: true })
    try {
      const provs = await api.listProviders()
      set({
        availableProviders: provs.providers,
        defaultProvider: provs.default,
      })
      // 当前 provider：localStorage > server default
      const cached = localStorage.getItem(LS.providerName)
      if (!cached) {
        set({ providerName: provs.default })
      }
    } catch (e: any) {
      set({ errorBanner: '后端不可用：' + e.message })
    }

    // 恢复会话
    const sid = localStorage.getItem(LS.currentSessionId)
    if (sid) {
      try {
        await get().switchSession(sid)
      } catch {
        localStorage.removeItem(LS.currentSessionId)
        await get().newSession()
      }
    } else {
      await get().newSession()
    }
    set({ loading: false })
  },

  async newSession() {
    set({ busy: true, errorBanner: null })
    try {
      const s = await api.createSession(get().providerName)
      localStorage.setItem(LS.currentSessionId, s.id)
      // 更新本地会话缓存
      const list = [
        { id: s.id, title: s.title, updated_at: s.updated_at },
        ...get().sessions.filter((x) => x.id !== s.id),
      ]
      writeJSON(LS.sessionsCache, list)
      set({
        sessionId: s.id,
        sessions: list,
        dsl: null,
        solution: null,
        svg: null,
        seq: 0,
        messages: [],
        selectedObjectId: null,
      })
    } catch (e: any) {
      set({ errorBanner: '创建会话失败：' + e.message })
    } finally {
      set({ busy: false })
    }
  },

  async switchSession(sid: string) {
    set({ busy: true, errorBanner: null })
    try {
      await api.getSession(sid)
      localStorage.setItem(LS.currentSessionId, sid)
      const [cur, msgs] = await Promise.all([
        api.getCurrentDSL(sid),
        api.getMessages(sid),
      ])
      set({
        sessionId: sid,
        dsl: cur.dsl,
        solution: cur.solution,
        svg: (cur as any).svg ?? null,
        seq: cur.seq,
        messages: msgs,
        selectedObjectId: null,
      })
    } catch (e: any) {
      throw e
    } finally {
      set({ busy: false })
    }
  },

  async deleteSession(sid: string) {
    await api.deleteSession(sid)
    const remaining = get().sessions.filter((s) => s.id !== sid)
    writeJSON(LS.sessionsCache, remaining)
    set({ sessions: remaining })
    if (get().sessionId === sid) {
      localStorage.removeItem(LS.currentSessionId)
      await get().newSession()
    }
  },

  async sendChat(nl: string) {
    const sid = get().sessionId
    if (!sid) return
    // ① 乐观更新：立即把用户气泡 + 思考中占位放进消息列表
    const tempId = -Date.now()
    const userMsg: Message = {
      id: tempId,
      role: 'user',
      content: nl,
      dsl_patch: null,
      llm_provider: null,
      tokens_in: null,
      tokens_out: null,
      latency_ms: null,
      error_kind: null,
      created_at: new Date().toISOString(),
      pending: true,
    }
    const thinkingMsg: Message = {
      id: tempId - 1,
      role: 'assistant',
      content: '__thinking__',
      dsl_patch: null,
      llm_provider: get().providerName,
      tokens_in: null,
      tokens_out: null,
      latency_ms: null,
      error_kind: null,
      created_at: new Date().toISOString(),
      pending: true,
    }
    set({
      messages: [...get().messages, userMsg, thinkingMsg],
      busy: true,
      errorBanner: null,
    })

    try {
      const res = await api.chat(sid, nl, get().providerName)
      if (res.ok && res.dsl) {
        set({
          dsl: res.dsl,
          solution: res.solution || null,
          svg: res.svg || null,
          seq: res.seq || 0,
        })
      } else if (res.error_kind === 'refuse') {
        // LLM 拒绝 — 不显示红色横幅，靠 messages 里的 assistant 气泡展示
      } else {
        set({ errorBanner: res.error || '生成失败' })
      }
      // 拉取权威消息列表替换乐观气泡
      const msgs = await api.getMessages(sid)
      set({ messages: msgs })

      // 更新会话缓存
      try {
        const session = await api.getSession(sid)
        const list = [
          {
            id: session.id,
            title: session.title || nl.slice(0, 20),
            updated_at: session.updated_at,
          },
          ...get().sessions.filter((x) => x.id !== sid),
        ]
        writeJSON(LS.sessionsCache, list)
        set({ sessions: list })
      } catch {
        /* ignore */
      }
    } catch (e: any) {
      // 网络 / 鉴权错误 → 顶部红条 + 移除占位消息
      const code = (e as any).code
      const detail = (e as any).detail
      set({
        errorBanner: e.message,
        messages: get().messages.filter((m) => m.id !== tempId && m.id !== tempId - 1),
      })
      // 同步从服务端拉一次，看看是否落了 assistant 错误消息
      try {
        const msgs = await api.getMessages(sid)
        set({ messages: msgs })
      } catch {
        /* ignore */
      }
    } finally {
      set({ busy: false })
    }
  },

  async applyPatch(ops: PatchOp[]) {
    const sid = get().sessionId
    if (!sid) return
    set({ busy: true, errorBanner: null })
    try {
      const res = await api.patch(sid, ops)
      set({
        dsl: res.dsl,
        solution: res.solution,
        svg: res.svg,
        seq: res.seq,
      })
    } catch (e: any) {
      set({ errorBanner: e.message })
    } finally {
      set({ busy: false })
    }
  },

  async undo() {
    const sid = get().sessionId
    if (!sid) return
    set({ busy: true })
    try {
      const res = await api.undo(sid)
      set({
        dsl: res.dsl,
        solution: res.solution,
        svg: (res as any).svg ?? null,
        seq: res.seq,
        selectedObjectId: null,
      })
    } catch (e: any) {
      set({ errorBanner: e.message })
    } finally {
      set({ busy: false })
    }
  },

  async redo() {
    const sid = get().sessionId
    if (!sid) return
    set({ busy: true })
    try {
      const res = await api.redo(sid)
      set({
        dsl: res.dsl,
        solution: res.solution,
        svg: (res as any).svg ?? null,
        seq: res.seq,
        selectedObjectId: null,
      })
    } catch (e: any) {
      set({ errorBanner: e.message })
    } finally {
      set({ busy: false })
    }
  },

  selectObject(id) {
    set({ selectedObjectId: id })
  },

  setProvider(name: string) {
    localStorage.setItem(LS.providerName, name)
    set({ providerName: name })
  },

  dismissError() {
    set({ errorBanner: null })
  },

  async sendFeedback(rating: 'good' | 'bad', comment?: string) {
    const sid = get().sessionId
    if (!sid) return
    try {
      await api.sendFeedback(sid, rating, comment)
    } catch (e: any) {
      set({ errorBanner: '反馈发送失败：' + e.message })
    }
  },
}))
