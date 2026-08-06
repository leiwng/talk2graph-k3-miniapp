const auth = require('../../utils/auth')
const { request } = require('../../utils/request')

Page({
  data: {
    nickname: '微信用户',
    email: '',
    avatarText: '微',
    quota: null,
  },

  onShow() {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    const user = auth.getUser() || {}
    const nickname = user.wechat_nickname || user.username || '微信用户'
    this.setData({
      nickname,
      email: user.email && !user.email.endsWith('@wechat.local') ? user.email : '',
      avatarText: nickname.slice(0, 1),
    })
    // 配额：失败静默（对齐计划）
    request('/payment/subscription')
      .then((res) => this.setData({ quota: res.entitlement }))
      .catch(() => {})
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后需要重新微信登录',
      success: (r) => {
        if (!r.confirm) return
        auth.clear()
        wx.removeStorageSync('t2g.current_session_id')
        wx.reLaunch({ url: '/pages/login/login' })
      },
    })
  },
})
