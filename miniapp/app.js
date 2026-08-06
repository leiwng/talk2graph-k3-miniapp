const store = require('./utils/store')

App({
  onLaunch() {
    // 会话 id 持久化，启动时由工作台页恢复
    store.setState({ sessionId: wx.getStorageSync('t2g.current_session_id') || null })
  },
})
