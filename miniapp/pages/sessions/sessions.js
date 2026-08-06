const store = require('../../utils/store')
const api = require('../../utils/api')
const auth = require('../../utils/auth')

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (isNaN(d.getTime())) return ''
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

Page({
  data: {
    sessions: [],
    currentId: null,
  },

  _unsub: null,

  onLoad() {
    this._unsub = store.subscribe((s) => this._render(s))
  },

  onUnload() {
    if (this._unsub) this._unsub()
  },

  onShow() {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    api.loadSessions().catch(() => {})
    this._render(store.getState())
  },

  _render(s) {
    this.setData({
      currentId: s.sessionId,
      sessions: s.sessions.map((it) => ({ ...it, updated_text: fmtTime(it.updated_at) })),
    })
  },

  async onNewSession() {
    try {
      await api.newSession()
      wx.switchTab({ url: '/pages/index/index' })
    } catch (e) {
      wx.showToast({ title: e.message || '创建失败', icon: 'none' })
    }
  },

  async onSwitch(e) {
    const sid = e.currentTarget.dataset.id
    if (sid === this.data.currentId) {
      wx.switchTab({ url: '/pages/index/index' })
      return
    }
    wx.showLoading({ title: '加载中', mask: true })
    try {
      await api.switchSession(sid)
      wx.switchTab({ url: '/pages/index/index' })
    } catch (err) {
      wx.showToast({ title: err.message || '切换失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  onRename(e) {
    const { id, title } = e.currentTarget.dataset
    wx.showModal({
      title: '重命名会话',
      editable: true,
      placeholderText: '输入新名称',
      content: title || '',
      success: async (r) => {
        if (!r.confirm || !r.content || !r.content.trim()) return
        try {
          await api.renameSession(id, r.content.trim())
        } catch (err) {
          wx.showToast({ title: err.message || '重命名失败', icon: 'none' })
        }
      },
    })
  },

  onDelete(e) {
    const sid = e.currentTarget.dataset.id
    wx.showModal({
      title: '删除会话',
      content: '删除后不可恢复，确定删除？',
      confirmColor: '#dc2626',
      success: async (r) => {
        if (!r.confirm) return
        try {
          await api.deleteSession(sid)
        } catch (err) {
          wx.showToast({ title: err.message || '删除失败', icon: 'none' })
        }
      },
    })
  },
})
