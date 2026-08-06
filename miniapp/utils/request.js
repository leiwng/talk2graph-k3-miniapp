// wx.request Promise 化 + Bearer + 401 处理 + 后端 friendly error 归一
// （对齐 Web 版 frontend/src/api/client.ts 的 request 行为）
const { API_BASE } = require('../config')
const auth = require('./auth')

// 后端 friendly error：{code, message, hint, detail} -> Error(message（hint）)，挂 code/detail
function normalizeError(data, statusCode) {
  let detail = data
  if (data && typeof data === 'object') {
    detail = data.detail !== undefined ? data.detail : (data.error !== undefined ? data.error : data)
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const msg = detail.hint ? `${detail.message}（${detail.hint}）` : detail.message
    const err = new Error(msg)
    err.code = detail.code
    err.detail = detail.detail
    return err
  }
  if (typeof detail === 'string' && detail) return new Error(detail)
  return new Error(`请求失败（${statusCode}）`)
}

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: API_BASE + '/api' + path,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        ...auth.authHeader(),
        ...(options.header || {}),
      },
      success(res) {
        if (res.statusCode === 401) {
          // 仅当原本有 token 时才清（对齐 Web 版）
          if (auth.getToken()) {
            auth.clear()
            wx.reLaunch({ url: '/pages/login/login' })
          }
          reject(new Error('请先登录'))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(normalizeError(res.data, res.statusCode))
          return
        }
        resolve(res.data)
      },
      fail(err) {
        reject(new Error('网络错误：' + (err.errMsg || 'unknown')))
      },
    })
  })
}

module.exports = { request, normalizeError }
