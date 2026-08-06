const auth = require('../../utils/auth')
const { request } = require('../../utils/request')

Page({
  data: {
    loading: false,
    error: '',
  },

  onLoad() {
    // 已有 token：直接进工作台（token 失效时由 401 兜底回这里）
    if (auth.getToken()) {
      wx.reLaunch({ url: '/pages/index/index' })
    }
  },

  onWxLogin() {
    if (this.data.loading) return
    this.setData({ loading: true, error: '' })
    wx.login({
      success: async (loginRes) => {
        if (!loginRes.code) {
          this.setData({ loading: false, error: 'wx.login 未返回 code' })
          return
        }
        try {
          const resp = await request('/auth/wechat/miniapp', {
            method: 'POST',
            data: { code: loginRes.code },
          })
          auth.save({ token: resp.token, user: resp.user })
          wx.reLaunch({ url: '/pages/index/index' })
        } catch (e) {
          this.setData({ loading: false, error: e.message || '登录失败，请重试' })
        }
      },
      fail: (err) => {
        this.setData({ loading: false, error: 'wx.login 失败：' + (err.errMsg || '') })
      },
    })
  },
})
