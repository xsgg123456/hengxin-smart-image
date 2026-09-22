import type { DemoState } from './demo-state'

const database = 'hengxin-framework-demo-v1'
export function demoKey(search = window.location.search) {
  const params = new URLSearchParams(search)
  return `${params.get('scenario') || 'default'}:${params.get('managementScenario') || 'default'}`
}
async function openStore(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(database, 1)
    request.onupgradeneeded = () => request.result.createObjectStore('states')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new Error('无法打开 Demo 存储，请检查浏览器存储权限'))
    request.onblocked = () => reject(new Error('Demo 存储被其他页面占用，请关闭旧的 Demo 页面后重试'))
  })
}
export async function readDemo(key: string): Promise<DemoState | undefined> {
  const db = await openStore()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction('states', 'readonly')
      const request = tx.objectStore('states').get(key)
      tx.oncomplete = () => {
        const value = request.result as DemoState | undefined
        if (value && value.schema !== 1) reject(new Error('Demo 数据版本不兼容，请重置当前演示场景'))
        else resolve(value)
      }
      tx.onerror = () => reject(new Error('Demo 数据读取失败'))
    })
  } finally { db.close() }
}
export async function writeDemo(key: string, state?: DemoState): Promise<void> {
  const db = await openStore()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('states', 'readwrite')
      const store = tx.objectStore('states')
      if (state) store.put(state, key)
      else store.delete(key)
      tx.oncomplete = () => resolve()
      tx.onabort = tx.onerror = () => reject(new Error('Demo 数据未能保存，可能是浏览器空间不足。请刷新后重试；本次操作未确认成功。'))
    })
  } finally { db.close() }
}
