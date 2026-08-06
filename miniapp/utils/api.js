// API 动作层：对齐 Web 版 store/index.ts 的会话/chat 流程
const { request } = require('./request')
const { chatStream } = require('./sse')
const store = require('./store')

const LS_SID = 't2g.current_session_id'

// stage -> 中文文案（照搬 Web 版 sendChat）
const STAGE_TEXT = {
  llm: '正在理解题意',
  patch: '正在修改图形',
  solve: '正在求解几何约束',
  repair: '图形不收敛，正在尝试修正',
  render: '正在渲染图形',
  fallback: '已切换到备选模型',
}

function _sid() {
  return store.getState().sessionId
}

async function loadSessions() {
  const items = await request('/sessions')
  store.setState({
    sessions: items.map((s) => ({
      id: s.id,
      title: s.title,
      updated_at: s.updated_at,
      message_count: s.message_count || 0,
      last_user_nl: s.last_user_nl || null,
    })),
  })
}

async function newSession() {
  store.setState({ busy: true, errorBanner: null })
  try {
    const s = await request('/session', { method: 'POST', data: { llm_provider: null } })
    wx.setStorageSync(LS_SID, s.id)
    const sessions = [
      { id: s.id, title: s.title, updated_at: s.updated_at, message_count: 0, last_user_nl: null },
      ...store.getState().sessions.filter((x) => x.id !== s.id),
    ]
    store.setState({
      sessionId: s.id,
      sessions,
      seq: 0,
      hasGraph: false,
      messages: [],
    })
  } catch (e) {
    store.setState({ errorBanner: '创建会话失败：' + e.message })
    throw e
  } finally {
    store.setState({ busy: false })
  }
}

async function switchSession(sid) {
  store.setState({ busy: true, errorBanner: null })
  try {
    await request(`/session/${sid}`)
    wx.setStorageSync(LS_SID, sid)
    const [cur, msgs] = await Promise.all([
      request(`/session/${sid}/dsl`),
      request(`/session/${sid}/messages`),
    ])
    store.setState({
      sessionId: sid,
      seq: cur.seq,
      hasGraph: !!(cur.dsl && cur.solution),
      messages: msgs,
    })
  } finally {
    store.setState({ busy: false })
  }
}

async function deleteSession(sid) {
  await request(`/session/${sid}`, { method: 'DELETE' })
  const remaining = store.getState().sessions.filter((s) => s.id !== sid)
  store.setState({ sessions: remaining })
  if (store.getState().sessionId === sid) {
    wx.removeStorageSync(LS_SID)
    await newSession()
  }
}

async function renameSession(sid, title) {
  const updated = await request(`/session/${sid}`, { method: 'PATCH', data: { title } })
  store.setState({
    sessions: store.getState().sessions.map((s) =>
      s.id === sid ? { ...s, title: updated.title, updated_at: updated.updated_at } : s
    ),
  })
}

async function ensureSession() {
  const sid = store.getState().sessionId
  if (sid) {
    try {
      await switchSession(sid)
      return
    } catch (e) {
      wx.removeStorageSync(LS_SID)
    }
  }
  await newSession()
}

// 发送自然语言作图请求（对齐 Web 版 sendChat：乐观更新 + SSE 流式 + 权威消息替换）
async function sendChat(nl) {
  const sid = _sid()
  if (!sid) return
  const tempId = -Date.now()
  const base = {
    dsl_patch: null,
    llm_provider: null,
    tokens_in: null,
    tokens_out: null,
    latency_ms: null,
    error_kind: null,
    created_at: new Date().toISOString(),
    pending: true,
  }
  const userMsg = { ...base, id: tempId, role: 'user', content: nl }
  const thinkingMsg = { ...base, id: tempId - 1, role: 'assistant', content: '__thinking__' }
  store.setState({
    messages: [...store.getState().messages, userMsg, thinkingMsg],
    busy: true,
    errorBanner: null,
  })

  // 流式状态：stage + 已识别对象 + 首字延迟标志（对齐 Web 版 __stream__ 协议）
  const streamState = { stage: '', objects: [], waiting: false }
  let streamClosed = false
  let firstTokenReceived = false
  let waitingTimer = null
  let flushTimer = null
  let pendingObjects = []

  const updateThinking = () => {
    const content = `__stream__:${JSON.stringify(streamState)}`
    store.setState({
      messages: store.getState().messages.map((m) =>
        m.id === tempId - 1 ? { ...m, content } : m
      ),
    })
  }
  const armWaitingTimer = () => {
    if (waitingTimer) clearTimeout(waitingTimer)
    waitingTimer = setTimeout(() => {
      if (!firstTokenReceived && !streamClosed) {
        streamState.waiting = true
        updateThinking()
      }
    }, 2000)
  }
  const onStage = (stage) => {
    streamState.stage = stage
    if (stage === 'fallback') {
      streamState.objects = []
      firstTokenReceived = false
      streamState.waiting = false
      armWaitingTimer()
      updateThinking()
      return
    }
    if (stage === 'llm') {
      streamState.waiting = false
      armWaitingTimer()
    } else {
      if (waitingTimer) { clearTimeout(waitingTimer); waitingTimer = null }
      streamState.waiting = false
    }
    updateThinking()
  }
  const onToken = () => {
    if (!firstTokenReceived) {
      firstTokenReceived = true
      if (waitingTimer) { clearTimeout(waitingTimer); waitingTimer = null }
      if (streamState.waiting) {
        streamState.waiting = false
        updateThinking()
      }
    }
  }
  const onObjectSeen = (id, kind) => {
    // 300ms 节流批量 flush（小程序没有 requestAnimationFrame）
    pendingObjects.push({ id, kind })
    if (!flushTimer) {
      flushTimer = setTimeout(() => {
        flushTimer = null
        if (streamClosed || pendingObjects.length === 0) return
        streamState.objects = streamState.objects.concat(pendingObjects)
        pendingObjects = []
        updateThinking()
      }, 300)
    }
  }

  try {
    const res = await chatStream(sid, nl, null, { onStage, onToken, onObjectSeen })
    if (res.ok && res.dsl) {
      store.setState({
        seq: res.seq || 0,
        hasGraph: true,
      })
    } else if (res.error_kind === 'refuse') {
      // 拒绝：靠 assistant 气泡展示，不出红条
    } else {
      store.setState({ errorBanner: res.error || '生成失败' })
    }
    // 拉权威消息列表替换乐观气泡
    const msgs = await request(`/session/${sid}/messages`)
    store.setState({ messages: msgs })
    // 更新会话缓存（title 由后端首条 NL 生成）
    try {
      const session = await request(`/session/${sid}`)
      const sessions = [
        {
          id: session.id,
          title: session.title || nl.slice(0, 20),
          updated_at: session.updated_at,
          message_count: session.message_count || 0,
          last_user_nl: session.last_user_nl || null,
        },
        ...store.getState().sessions.filter((x) => x.id !== sid),
      ]
      store.setState({ sessions })
    } catch (e) { /* ignore */ }
    return res
  } catch (e) {
    store.setState({
      errorBanner: e.message,
      messages: store.getState().messages.filter((m) => m.id !== tempId && m.id !== tempId - 1),
    })
    try {
      const msgs = await request(`/session/${sid}/messages`)
      store.setState({ messages: msgs })
    } catch (e2) { /* ignore */ }
    throw e
  } finally {
    streamClosed = true
    if (waitingTimer) clearTimeout(waitingTimer)
    if (flushTimer) clearTimeout(flushTimer)
    store.setState({ busy: false })
  }
}

async function undo() {
  const sid = _sid()
  if (!sid) return null
  const res = await request(`/session/${sid}/undo`, { method: 'POST' })
  store.setState({ seq: res.seq, hasGraph: !!(res.dsl && res.solution) })
  return res
}

async function redo() {
  const sid = _sid()
  if (!sid) return null
  const res = await request(`/session/${sid}/redo`, { method: 'POST' })
  store.setState({ seq: res.seq, hasGraph: !!(res.dsl && res.solution) })
  return res
}

async function sendFeedback(rating, comment) {
  const sid = _sid()
  if (!sid) return
  await request(`/session/${sid}/feedback`, {
    method: 'POST',
    data: { rating, comment: comment || null },
  })
}

module.exports = {
  STAGE_TEXT,
  loadSessions,
  newSession,
  switchSession,
  deleteSession,
  renameSession,
  ensureSession,
  sendChat,
  undo,
  redo,
  sendFeedback,
}
