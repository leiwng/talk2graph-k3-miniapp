// 登录态存储（对齐 Web 版 frontend/src/api/auth.ts 的 t2g.auth 结构）
const KEY = 't2g.auth'

function load() {
  try {
    return wx.getStorageSync(KEY) || null
  } catch (e) {
    return null
  }
}

function save(auth) {
  wx.setStorageSync(KEY, auth)
}

function clear() {
  wx.removeStorageSync(KEY)
}

function getToken() {
  const a = load()
  return a && a.token ? a.token : null
}

function getUser() {
  const a = load()
  return a && a.user ? a.user : null
}

function authHeader() {
  const t = getToken()
  return t ? { Authorization: 'Bearer ' + t } : {}
}

module.exports = { load, save, clear, getToken, getUser, authHeader }
