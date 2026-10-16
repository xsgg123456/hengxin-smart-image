import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Asset } from './state'

const storageKey = 'hx-materials-archive-preview-v1-hidden'
type Saved = { id: string; name: string; image: boolean; fingerprint: string; file: Blob }
async function database() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open('hx-materials-archive-preview-v1', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('files', { keyPath: 'id' })
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
async function persist(value?: Saved, clear = false): Promise<Saved[]> {
  const db = await database()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('files', 'readwrite'), store = tx.objectStore('files')
    if (clear) store.clear()
    if (value) store.put(value)
    const request = store.getAll()
    tx.oncomplete = () => { db.close(); resolve(request.result as Saved[]) }
    tx.onerror = () => { db.close(); reject(tx.error) }
  })
}
async function fingerprint(file: Blob) {
  const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('')
}
export function useMaterials(seeds: Asset[], urls: Set<string>) {
  const records = ref<Asset[]>(seeds.map(a => ({ ...a })))
  const hidden = ref<string[]>([])
  try { hidden.value = JSON.parse(localStorage.getItem(storageKey) || '[]') } catch { /* 本地预览首次启动 */ }
  const key = (asset: Asset) => asset.fingerprint || asset.url
  const materials = computed(() => {
    const seen = new Set<string>()
    return records.value.filter(a => {
      const id = key(a)
      if (hidden.value.includes(id) || seen.has(id)) return false
      seen.add(id); return true
    })
  })
  const ready = Promise.all(seeds.map(async a => {
    const response = await fetch(a.url)
    if (!response.ok) throw Error('示例文件加载失败')
    const hash = await fingerprint(await response.blob())
    records.value.filter(b => b.url === a.url).forEach(b => { b.fingerprint = hash })
  })).then(async () => {
    for (const item of await persist()) {
      const url = URL.createObjectURL(item.file); urls.add(url)
      records.value.push({ ...item, url, caption: '上传附件 · 本地预览' })
    }
  }).catch(() => { ElMessage.warning('预览素材初始化失败，请刷新后重试') })
  function saveHidden() { localStorage.setItem(storageKey, JSON.stringify(hidden.value)) }
  async function removeMaterial(asset: Asset) {
    await ready
    try { await ElMessageBox.confirm('仅从任务素材列表移除，不影响历史消息和已发送文件。', `移除 ${asset.name}`, { confirmButtonText: '移除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
    const row = records.value.find(a => a.id === asset.id) || asset
    hidden.value = [...new Set([...hidden.value, key(row)])]; saveHidden()
    ElMessage.success('已从列表移除，历史消息和待发送附件保留')
  }
  async function register(file: File, image: boolean, restore = true): Promise<Asset> {
    await ready
    const hash = await fingerprint(file), existing = records.value.find(a => a.fingerprint === hash)
    if (existing) {
      const removed = hidden.value.includes(hash)
      if (restore) {
        hidden.value = hidden.value.filter(h => h !== hash); saveHidden()
        ElMessage.info(removed ? '已恢复到任务素材列表' : '该文件已在任务素材中')
      }
      return existing
    }
    const id = crypto.randomUUID(), url = URL.createObjectURL(file); urls.add(url)
    await persist({ id, name: file.name, image, fingerprint: hash, file })
    const asset = { id, name: file.name, image, fingerprint: hash, url, caption: `${(file.size / 1024).toFixed(1)} KB · 上传附件` }
    records.value.push(asset)
    return asset
  }
  async function rememberSent(files: Asset[]) {
    await ready
    for (const asset of files) {
      if (records.value.some(a => a.id === asset.id || a.url === asset.url)) continue
      const response = await fetch(asset.url)
      if (!response.ok) throw Error('附件读取失败')
      const blob = await response.blob()
      await register(new File([blob], asset.name, { type: blob.type }), asset.image, false)
    }
  }
  async function demoDuplicate() {
    await ready
    const asset = seeds.find(a => a.image)!
    try { const response = await fetch(asset.url); await register(new File([await response.blob()], '重命名的同一张图.jpg', { type: 'image/jpeg' }), true) }
    catch { ElMessage.error('示例文件读取失败，请重试') }
  }
  async function resetMaterials() {
    await ready
    await persist(undefined, true)
    hidden.value = []; saveHidden()
    records.value = records.value.filter(a => seeds.some(s => s.id === a.id))
    ElMessage.success('已恢复本地预览的示例素材')
  }
  return { materials, removeMaterial, register, rememberSent, demoDuplicate, resetMaterials }
}
