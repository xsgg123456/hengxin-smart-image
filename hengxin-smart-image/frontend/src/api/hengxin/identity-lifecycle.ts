import { identity } from './identity'

/** 锁定同步发生在浏览器事件内，早于 Vue 下一次渲染及 bfcache 快照。 */
export function installIdentityLifecycle(options: {
  window: Window; document: Document; resume: () => Promise<void>; lock: () => void
}) {
  const { window: win, document: doc } = options
  let suspended = false
  const suspend = () => {
    options.lock()
    if (!suspended) { suspended = true; identity.advance('suspended') }
  }
  const resume = () => {
    if (!suspended) return
    suspended = false
    options.lock()
    void options.resume()
  }
  const visibility = () => { if (doc.visibilityState === 'hidden') suspend(); else resume() }
  const pageshow = (event: PageTransitionEvent) => { if (event.persisted) suspend(); resume() }
  const storage = (event: StorageEvent) => {
    if (event.key === 'hengxin:logout' && event.newValue) identity.advance('invalid')
  }
  win.addEventListener('pagehide', suspend)
  win.addEventListener('pageshow', pageshow)
  doc.addEventListener('visibilitychange', visibility)
  win.addEventListener('storage', storage)
  return () => {
    win.removeEventListener('pagehide', suspend)
    win.removeEventListener('pageshow', pageshow)
    doc.removeEventListener('visibilitychange', visibility)
    win.removeEventListener('storage', storage)
  }
}

export function broadcastLogout() {
  identity.advance('invalid')
  // 接收端不再广播；只传随机通知，不持久化身份或业务数据。
  try { localStorage.setItem('hengxin:logout', crypto.randomUUID()) } catch { /* 存储不可用时服务端仍重验 */ }
}
