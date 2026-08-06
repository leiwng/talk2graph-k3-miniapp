const store = require('../../utils/store')
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const { API_BASE } = require('../../config')

// 原始 Message -> 渲染视图模型（含 __thinking__ / __stream__ 协议解析）
function toViewModel(m) {
  const vm = { id: m.id, role: m.role, kind: 'text', cls: '', text: '', fallback: !!m.fallback }
  if (m.content === '__thinking__') {
    vm.kind = 'thinking'
    return vm
  }
  if (typeof m.content === 'string' && m.content.startsWith('__stream__:')) {
    vm.kind = 'stream'
    try {
      const s = JSON.parse(m.content.slice('__stream__:'.length))
      vm.stageText = api.STAGE_TEXT[s.stage] || s.stage || '正在处理'
      vm.waiting = !!s.waiting
      const objs = (s.objects || []).slice(0, 8).map((o) => o.id)
      vm.objectsText = objs.join('、')
    } catch (e) {
      vm.stageText = '正在处理'
    }
    return vm
  }
  vm.text = m.content
  if (m.role === 'assistant' && m.error_kind) {
    vm.cls = 'err-' + m.error_kind // refuse 黄 / solve|patch 紫 / network 红
  } else if (m.role === 'assistant') {
    // DSL JSON 原文 -> 摘要（对齐 Web 版 ChatPanel）
    try {
      const j = JSON.parse(m.content)
      const objs = (j.objects && j.objects.length) || 0
      const cons = (j.constraints && j.constraints.length) || 0
      vm.text = `✓ 图形已更新（${objs} 个对象，${cons} 条约束）`
    } catch (e) { /* 文本消息原样 */ }
  }
  return vm
}

Page({
  data: {
    messages: [],
    busy: false,
    errorBanner: null,
    inputValue: '',
    imgPath: '',
    canvasLoading: false,
    scrollInto: '',
  },

  _unsub: null,
  _loadedSid: null,
  _loadedSeq: -1,

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
    const s = store.getState()
    if (!s.sessionId) {
      // 首次进入：恢复或创建会话
      api.ensureSession().catch(() => {})
    } else if (this._loadedSid !== s.sessionId) {
      // 从会话页切了会话：强制刷新画板
      this._loadedSeq = -1
    }
    this._render(s)
  },

  _render(s) {
    const vms = s.messages.map(toViewModel)
    const last = vms.length ? vms[vms.length - 1] : null
    this.setData({
      messages: vms,
      busy: s.busy,
      errorBanner: s.errorBanner,
      scrollInto: last ? `msg-${last.id}` : '',
    })
    // seq 变化 -> 拉新 PNG
    if (s.sessionId && s.hasGraph && (s.seq !== this._loadedSeq || s.sessionId !== this._loadedSid)) {
      this._loadImage(s)
    } else if (!s.hasGraph && this.data.imgPath) {
      this.setData({ imgPath: '' })
      this._loadedSeq = -1
    }
  },

  _loadImage(s) {
    this._loadedSid = s.sessionId
    this._loadedSeq = s.seq
    this.setData({ canvasLoading: true })
    wx.downloadFile({
      url: `${API_BASE}/api/export/${s.sessionId}.png?t=${s.seq}`,
      header: auth.authHeader(),
      success: (res) => {
        if (res.statusCode === 200) {
          this.setData({ imgPath: res.tempFilePath, canvasLoading: false })
        } else {
          this.setData({ canvasLoading: false })
        }
      },
      fail: () => this.setData({ canvasLoading: false }),
    })
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value })
  },

  async onSend() {
    const nl = this.data.inputValue.trim()
    if (!nl || this.data.busy) return
    this.setData({ inputValue: '' })
    try {
      await api.sendChat(nl)
    } catch (e) {
      // errorBanner 已在 store 里
    }
  },

  async onNewSession() {
    if (this.data.busy) return
    try {
      await api.newSession()
    } catch (e) { /* banner 已提示 */ }
  },

  async onUndo() {
    if (this.data.busy) return
    try {
      await api.undo()
    } catch (e) {
      wx.showToast({ title: e.message || '撤销失败', icon: 'none' })
    }
  },

  async onRedo() {
    if (this.data.busy) return
    try {
      await api.redo()
    } catch (e) {
      wx.showToast({ title: e.message || '重做失败', icon: 'none' })
    }
  },

  onSaveImage() {
    if (!this.data.imgPath) return
    wx.saveImageToPhotosAlbum({
      filePath: this.data.imgPath,
      success: () => wx.showToast({ title: '已保存到相册', icon: 'success' }),
      fail: (err) => {
        if (err.errMsg && err.errMsg.includes('auth')) {
          wx.showModal({
            title: '需要相册权限',
            content: '请在设置中允许保存图片到相册',
            confirmText: '去设置',
            success: (r) => {
              if (r.confirm) wx.openSetting()
            },
          })
        } else {
          wx.showToast({ title: '保存失败', icon: 'none' })
        }
      },
    })
  },

  onDismissError() {
    store.setState({ errorBanner: null })
  },

  onShareAppMessage() {
    return {
      title: '话图 T2G - 用一句话，画出几何图形',
      path: '/pages/index/index',
    }
  },
})
