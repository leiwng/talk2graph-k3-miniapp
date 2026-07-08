import { create } from 'zustand'
import { api } from '../api/client'
import { getStoredToken } from '../api/auth'
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

  activeTab: 'chat' | 'canvas' | 'objects'
  debugUI: boolean

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
  setActiveTab: (t: 'chat' | 'canvas' | 'objects') => void
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

  activeTab: 'chat',
  debugUI: false,

  async init() {
    set({ loading: true })
    try {
      // 拉 /api/health 拿 debug_ui 标志
      try {
        const h = await api.health()
        set({ debugUI: h.debug_ui === true })
      } catch {
        /* 后端旧版本不带 debug_ui 字段，默认 false */
      }
      const provs = await api.listProviders()
      set({
        availableProviders: provs.providers,
        defaultProvider: provs.default,
      })
      // 当前 provider：localStorage > server default；若缓存的 provider 未配置则回退到 default
      const cached = localStorage.getItem(LS.providerName)
      const enabledNames = provs.providers.filter((p) => p.enabled).map((p) => p.name)
      if (!cached || !enabledNames.includes(cached)) {
        set({ providerName: provs.default })
      }
    } catch (e: any) {
      set({ errorBanner: '后端不可用：' + e.message })
    }

    // V2-F.1：仅登录用户恢复会话；未登录用户在落地页不需要 session
    if (getStoredToken()) {
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

    // V2-D：stage → 中文文案
    const stageText: Record<string, string> = {
      llm: '正在理解题意',
      patch: '正在修改图形',
      solve: '正在求解几何约束',
      repair: '图形不收敛，正在尝试修正',
      render: '正在渲染图形',
    }

    // 流式状态：当前 stage + 已识别对象列表 + 首字延迟期标志
    // thinking 气泡 content 用 `__stream__:<json>` 表示，ChatPanel 解析渲染
    // 改进 3：waiting=true 表示 LLM 首字延迟期（stage=llm 后 2s 还没收到 token）
    //   显示"AI 正在准备输出..."次级提示，避免干等
    // 改进 4：onObjectSeen 不直接 set，而是用 RAF 批量 flush，避免每对象触发 re-render
    const streamState: {
      stage: string
      objects: Array<{ id: string; kind: string }>
      waiting: boolean
    } = {
      stage: '',
      objects: [],
      waiting: false,
    }
    let pendingObjects: Array<{ id: string; kind: string }> = []
    let rafHandle: number | null = null
    let firstTokenReceived = false
    let waitingTimer: number | null = null
    let streamClosed = false

    const updateThinking = () => {
      const content = `__stream__:${JSON.stringify(streamState)}`
      const msgs = get().messages.map((m) =>
        m.id === tempId - 1 ? { ...m, content } : m
      )
      set({ messages: msgs })
    }
    const flushPending = () => {
      rafHandle = null
      if (streamClosed || pendingObjects.length === 0) return
      for (const o of pendingObjects) {
        streamState.objects.push(o)
      }
      pendingObjects = []
      updateThinking()
    }
    const scheduleFlush = () => {
      if (rafHandle === null) {
        rafHandle = requestAnimationFrame(flushPending)
      }
    }
    const onStage = (stage: string) => {
      streamState.stage = stage
      // V2-E：fallback 切换模型时清空之前 provider 推的对象，避免重复显示
      if (stage === 'fallback') {
        streamState.objects = []
        // 重置首字延迟：新 provider 重新计时
        firstTokenReceived = false
        streamState.waiting = false
        if (waitingTimer !== null) {
          clearTimeout(waitingTimer)
          waitingTimer = null
        }
        // 2 秒后若新 provider 也没收到 token，再次显示准备提示
        waitingTimer = window.setTimeout(() => {
          if (!firstTokenReceived && !streamClosed) {
            streamState.waiting = true
            updateThinking()
          }
        }, 2000)
        updateThinking()
        return
      }
      if (stage === 'llm') {
        streamState.waiting = false
        // 2 秒后若还没收到 token，显示准备提示
        waitingTimer = window.setTimeout(() => {
          if (!firstTokenReceived && !streamClosed) {
            streamState.waiting = true
            updateThinking()
          }
        }, 2000)
      } else {
        // 离开 llm 阶段：清除等待状态
        if (waitingTimer !== null) {
          clearTimeout(waitingTimer)
          waitingTimer = null
        }
        streamState.waiting = false
      }
      updateThinking()
    }
    const onToken = (_text: string) => {
      // 不显示原始 token 内容，只用于标记首字到达
      if (!firstTokenReceived) {
        firstTokenReceived = true
        if (waitingTimer !== null) {
          clearTimeout(waitingTimer)
          waitingTimer = null
        }
        if (streamState.waiting) {
          streamState.waiting = false
          updateThinking()
        }
      }
    }
    const onObjectSeen = (id: string, kind: string) => {
      pendingObjects.push({ id, kind })
      scheduleFlush()
    }

    try {
      // 生产模式（debugUI=false）：不传 provider，让后端按 fallback chain 自动选
      // 调试模式：传用户在 ProviderSwitch 选的 providerName
      const providerForReq = get().debugUI ? get().providerName : null
      const res = await api.chatStream(
        sid, nl, providerForReq, onStage, onToken, onObjectSeen
      )
      if (res.ok && res.dsl) {
        set({
          dsl: res.dsl,
          solution: res.solution || null,
          svg: res.svg || null,
          seq: res.seq || 0,
          activeTab: 'canvas',
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
      // V2-D 改进：清理 RAF + 等待定时器，防止泄漏
      streamClosed = true
      if (rafHandle !== null) {
        cancelAnimationFrame(rafHandle)
        rafHandle = null
      }
      if (waitingTimer !== null) {
        clearTimeout(waitingTimer)
        waitingTimer = null
      }
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

  setActiveTab(t) {
    set({ activeTab: t })
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
