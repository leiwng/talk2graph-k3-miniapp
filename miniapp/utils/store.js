// 轻量全局状态（替代 Web 版 Zustand）：getState / setState / subscribe
const state = {
  sessionId: null,
  sessions: [], // [{id, title, updated_at, message_count, last_user_nl}]
  seq: 0,
  hasGraph: false, // 当前会话是否已有图（决定画板是否拉 PNG）
  messages: [], // 原始 Message 对象（含 pending / __thinking__ / __stream__ 协议）
  busy: false,
  errorBanner: null,
}

const listeners = new Set()

function getState() {
  return state
}

function setState(patch) {
  Object.assign(state, patch)
  listeners.forEach((fn) => {
    try { fn(state) } catch (e) { /* 页面已卸载等情况忽略 */ }
  })
}

// 返回取消订阅函数
function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

module.exports = { getState, setState, subscribe }
