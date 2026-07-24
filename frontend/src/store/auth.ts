import { create } from 'zustand'
import { authApi, loadStoredAuth, storeAuth, clearStoredAuth, getStoredToken } from '../api/auth'
import type { User } from '../api/types'
import { useStore } from './index'

const AUTH_CHECK_TTL_MS = 30_000  // 30s 缓存：避免每次切路由都打 /me

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean  // 启动时初次 checkAuth 的 loading 状态
  lastAuthCheck: number  // timestamp ms

  // actions
  init: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, username: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<boolean>
  refreshUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  lastAuthCheck: 0,

  init: async () => {
    const stored = loadStoredAuth()
    if (stored) {
      set({ user: stored.user, token: stored.token, isAuthenticated: true })
      // 后台异步校验 token 是否仍然有效（不阻塞 UI）
      void get().checkAuth().finally(() => set({ isLoading: false }))
    } else {
      set({ isLoading: false })
    }
  },

  login: async (email, password) => {
    const resp = await authApi.login(email, password)
    storeAuth(resp)
    set({ user: resp.user, token: resp.token, isAuthenticated: true, lastAuthCheck: Date.now() })
  },

  register: async (email, password, username) => {
    const resp = await authApi.register(email, password, username)
    storeAuth(resp)
    set({ user: resp.user, token: resp.token, isAuthenticated: true, lastAuthCheck: Date.now() })
  },

  logout: async () => {
    try {
      // best-effort 调后端 logout（让服务端写 audit）
      if (getStoredToken()) await authApi.logout()
    } catch {
      // 网络错误忽略
    }
    clearStoredAuth()
    set({ user: null, token: null, isAuthenticated: false, lastAuthCheck: 0 })
    // P0：清空 app store 的 sessions 缓存（避免下次登录看到上一个账号的会话列表）
    try {
      useStore.setState({
        sessions: [],
        sessionId: null,
        messages: [],
        dsl: null,
        solution: null,
        svg: null,
        seq: 0,
        drawerOpen: false,
      })
      localStorage.removeItem('t2g.current_session_id')
    } catch {
      /* ignore */
    }
  },

  checkAuth: async () => {
    const { isAuthenticated, lastAuthCheck } = get()
    if (!isAuthenticated) {
      set({ isLoading: false })
      return false
    }
    // 30s 内不重复校验
    const now = Date.now()
    if (lastAuthCheck && now - lastAuthCheck < AUTH_CHECK_TTL_MS) {
      return true
    }
    try {
      const user = await authApi.me()
      set({ user, lastAuthCheck: now, isAuthenticated: true, isLoading: false })
      return true
    } catch {
      // token 失效
      clearStoredAuth()
      set({ user: null, token: null, isAuthenticated: false, isLoading: false, lastAuthCheck: 0 })
      return false
    }
  },

  refreshUser: async () => {
    const user = await authApi.me()
    const stored = loadStoredAuth()
    if (stored) {
      storeAuth({ ...stored, user })
    }
    set({ user })
  },
}))
