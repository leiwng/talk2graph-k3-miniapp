// SSE 流式 chat：wx.request enableChunked 接收 /api/session/{sid}/chat/stream
// （对齐 Web 版 client.ts chatStream / _parseSseFrame 的事件协议）
const { API_BASE } = require('../config')
const auth = require('./auth')
const { normalizeError } = require('./request')

// 增量 UTF-8 解码：chunk 边界可能切断多字节字符（小程序没有可靠的 TextDecoder）
function createDecoder() {
  let pending = []
  return function decode(arrayBuffer) {
    const input = new Uint8Array(arrayBuffer)
    const bytes = pending.length ? pending.concat(Array.from(input)) : Array.from(input)
    let out = ''
    let i = 0
    while (i < bytes.length) {
      const b = bytes[i]
      let n
      if (b < 0x80) n = 1
      else if ((b & 0xe0) === 0xc0) n = 2
      else if ((b & 0xf0) === 0xe0) n = 3
      else if ((b & 0xf8) === 0xf0) n = 4
      else { i += 1; continue } // 非法字节，跳过
      if (i + n > bytes.length) break // 不完整序列，留给下一 chunk
      let cp
      if (n === 1) cp = b
      else if (n === 2) cp = ((b & 0x1f) << 6) | (bytes[i + 1] & 0x3f)
      else if (n === 3) cp = ((b & 0x0f) << 12) | ((bytes[i + 1] & 0x3f) << 6) | (bytes[i + 2] & 0x3f)
      else cp = ((b & 0x07) << 18) | ((bytes[i + 1] & 0x3f) << 12) | ((bytes[i + 2] & 0x3f) << 6) | (bytes[i + 3] & 0x3f)
      out += String.fromCodePoint(cp)
      i += n
    }
    pending = bytes.slice(i)
    return out
  }
}

function decodeAll(arrayBuffer) {
  return createDecoder()(arrayBuffer)
}

// SSE 帧：event: X\ndata: {json}（对齐后端 chat_stream._sse）
function parseFrame(frame) {
  let event = ''
  let dataStr = ''
  const lines = frame.split('\n')
  for (const line of lines) {
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) dataStr += line.slice(6)
  }
  if (!event || !dataStr) return null
  try {
    return { event, data: JSON.parse(dataStr) }
  } catch (e) {
    return null
  }
}

// callbacks: { onStage(stage), onToken(text), onObjectSeen(id, kind) }
// resolve: ChatResult（done 事件 data）；reject: Error（挂 code/detail）
function chatStream(sid, nl, provider, callbacks) {
  callbacks = callbacks || {}
  return new Promise((resolve, reject) => {
    const decode = createDecoder()
    let buf = ''
    let result = null
    let done = false

    function failOnce(err) {
      if (done) return
      done = true
      reject(err)
    }

    function dispatch(frame) {
      const evt = parseFrame(frame)
      if (!evt) return
      if (evt.event === 'stage') {
        callbacks.onStage && callbacks.onStage(evt.data.stage)
      } else if (evt.event === 'token') {
        callbacks.onToken && callbacks.onToken(evt.data.text)
      } else if (evt.event === 'object_seen') {
        callbacks.onObjectSeen && callbacks.onObjectSeen(evt.data.id, evt.data.kind)
      } else if (evt.event === 'done') {
        result = evt.data
      } else if (evt.event === 'error') {
        const d = evt.data || {}
        const msg = d.hint ? `${d.message}（${d.hint}）` : (d.message || 'stream error')
        const err = new Error(msg)
        err.code = d.code
        err.detail = d.detail
        failOnce(err)
      }
    }

    function flush() {
      let i
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, i)
        buf = buf.slice(i + 2)
        dispatch(frame)
        if (done) return
      }
    }

    const task = wx.request({
      url: `${API_BASE}/api/session/${sid}/chat/stream`,
      method: 'POST',
      enableChunked: true,
      responseType: 'arraybuffer',
      header: {
        'Content-Type': 'application/json',
        ...auth.authHeader(),
      },
      data: { nl, provider: provider || null },
      success(res) {
        if (done) return
        if (res.statusCode === 401) {
          if (auth.getToken()) {
            auth.clear()
            wx.reLaunch({ url: '/pages/login/login' })
          }
          failOnce(new Error('请先登录'))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          // 非流式错误：body 整体返回（arraybuffer）
          let data = res.data
          if (data instanceof ArrayBuffer) {
            try { data = JSON.parse(decodeAll(data)) } catch (e) { data = decodeAll(data) }
          }
          failOnce(normalizeError(data, res.statusCode))
          return
        }
        flush() // 兜底处理末尾无 \n\n 前已积满的帧
        if (result) {
          done = true
          resolve(result)
        } else {
          failOnce(new Error('stream ended without done event'))
        }
      },
      fail(err) {
        failOnce(new Error('网络错误：' + (err.errMsg || 'unknown')))
      },
    })

    task.onChunkReceived((resp) => {
      if (done) return
      buf += decode(resp.data)
      flush()
    })
  })
}

module.exports = { chatStream }
