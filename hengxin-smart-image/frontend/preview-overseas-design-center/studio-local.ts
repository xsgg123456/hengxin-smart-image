import type { Asset, Studio, StudioConversation, StudioTurn, TurnInput } from '@/api/overseas/studio'
import type { TaskDetail } from '@/api/overseas/tasks'

export interface StudioEntry {
  id: string
  sku: string
  title: string
  brand: string
  platform: string
  designType?: 'custom' | 'platform'
  productName?: string
  remarks?: string
  designer?: string
  language?: string
  materials?: { name: string; file?: Blob }[]
}

const actor = { id: 'design-center-preview', name: '设计师' }
const now = () => new Date().toISOString()
const token = () => Math.random().toString(36).slice(2, 12)
const base = (id: string) => `/api/overseas/v1/tasks/${encodeURIComponent(id)}/studio`

export function studioTask(entry: StudioEntry): TaskDetail {
  return {
    id: entry.id, name: entry.title, productName: entry.productName || entry.title,
    brand: entry.brand, platform: entry.platform, designType: entry.designType, language: entry.language, market: '',
    remarks: entry.remarks || '', skus: [{ code: entry.sku }], status: 'studio', workflow: 'studio',
    createdAt: now(), updatedAt: now(), version: 1, createdBy: actor,
    designer: { ...actor, name: entry.designer || actor.name, status: 'active', eligible: true },
    capabilities: ['task.design'], events: [],
  }
}

type Session = { row: StudioConversation; turns: StudioTurn[] }
type Workspace = { sessions: Session[]; materials: Asset[]; files: Map<string, Blob> }
const workspaces = new Map<string, Workspace>()
const thumbnails = new Map<string, string>()

export function localStudioThumbnail(asset: { url: string }) {
  return thumbnails.get(asset.url) || ''
}

function newSession(name: string, id = token()): Session {
  const date = now()
  return {
    row: { id, name, version: 1, createdAt: date, updatedAt: date, activeTurnId: null, status: 'empty', turnCount: 0 },
    turns: [],
  }
}

function appendTurn(session: Session, text: string, reply: string, assets: Asset[], skillName: string | null = null) {
  const date = now()
  session.turns.push({
    id: token(), jobId: token(), conversationId: session.row.id, jobVersion: 1,
    text, reply, skillName, status: 'succeeded', error: null, createdAt: date, replyAt: date,
    replyTimeSource: 'message', actor, attachments: assets, referencePictures: [], pictures: [],
  })
  Object.assign(session.row, { turnCount: session.turns.length, updatedAt: date, status: 'succeeded', version: session.row.version + 1 })
}

function addMaterial(workspace: Workspace, id: string, url: string, name: string, file?: Blob): Asset {
  const asset: Asset = { id, name, url, source: id.startsWith('task:') ? 'task' : 'upload', contentType: file?.type || 'application/octet-stream', sizeBytes: file?.size || 0 }
  workspace.materials.push(asset)
  if (file) workspace.files.set(url, file)
  return asset
}

function workspaceFor(entry: StudioEntry): Workspace {
  const existing = workspaces.get(entry.id)
  if (existing) return existing
  const session = newSession('会话 1', `${entry.id}-first`)
  const workspace: Workspace = { sessions: [session], materials: [], files: new Map() }
  for (const material of entry.materials || []) {
    const file = material.file instanceof Blob ? material.file : undefined
    const id = `${file ? 'material' : 'metadata'}-${token()}`
    addMaterial(workspace, `task:${id}`, `/api/overseas/v1/materials/${id}/content`, material.name, file)
  }
  if (!entry.id.startsWith('HX-N')) {
    const brief = entry.remarks || `为 ${entry.productName || entry.title} 准备 ${entry.platform} 产品图，SKU 为 ${entry.sku}。`
    appendTurn(session, brief, '已整理这项任务的图需。可以继续补充需要突出的产品细节，或上传参考素材。', [])
  }
  workspaces.set(entry.id, workspace)
  return workspace
}

const skill = { id: 'product-imagery', name: 'product-imagery', displayName: '电商产品图设计', description: '结合图需和产品素材整理电商图片方案。' }
function snapshot(entry: StudioEntry, workspace: Workspace, session?: Session): Studio {
  return {
    taskId: entry.id, taskVersion: 1, completed: false, reopened: false, archiveId: null,
    activeTurnId: null, conversationId: session?.row.id || null, conversations: workspace.sessions.map(s => s.row),
    activeConversationCount: 0, maxConversations: 10, materials: workspace.materials, skills: entry.designType === 'custom' ? [] : [skill], turns: session?.turns || [],
  }
}

const json = (body: unknown, status = 200) => Response.json(body, { status })
const unavailable = () => json({ detail: '当前本地预览没有此文件或操作。' }, 404)

// The production components keep their normal request/response validation. Business requests
// terminate here, including unknown endpoints, while Vite can still load its local modules.
export function installStudioPreview(entry: StudioEntry) {
  const workspace = workspaceFor(entry)
  const nativeFetch = window.fetch
  const endpoint = base(entry.id)
  const cacheThumbnail = (url: string, blob: Blob) => {
    if (blob.type.startsWith('image/') && !thumbnails.has(url)) thumbnails.set(url, URL.createObjectURL(blob))
  }
  workspace.files.forEach((blob, url) => cacheThumbnail(url, blob))
  const localFetch: typeof fetch = async (input, options = {}) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.href)
    if (!url.pathname.startsWith('/api/')) return nativeFetch(input, options)
    const method = options.method || 'GET'
    const file = workspace.files.get(url.pathname)
    if (file) return new Response(method === 'HEAD' ? null : file, {
      headers: { 'Content-Type': file.type || 'application/octet-stream', 'Content-Length': String(file.size) },
    })
    if (url.pathname !== endpoint && !url.pathname.startsWith(endpoint + '/')) return unavailable()
    const path = url.pathname.slice(endpoint.length)
    const body = typeof options.body === 'string' ? JSON.parse(options.body) : {}
    const sessionId = body.conversationId || url.searchParams.get('conversationId')
    let session = sessionId ? workspace.sessions.find(s => s.row.id === sessionId) : workspace.sessions[0]
    if (sessionId && !session) return unavailable()
    if (!path && method === 'GET') return json(snapshot(entry, workspace, session))
    if (path === '/transcript' || path === '/events') return json({ items: [], cursor: 0, hasMore: false })
    if (path.endsWith('/recoverable-files')) return json({ items: [], busy: false })
    if (path === '/conversations' && method === 'POST') {
      session = newSession(body.name || `会话 ${workspace.sessions.length + 1}`)
      workspace.sessions.push(session)
    } else if (path.startsWith('/conversations/')) {
      session = workspace.sessions.find(s => s.row.id === decodeURIComponent(path.slice('/conversations/'.length)))
      if (!session) return unavailable()
      if (method === 'PATCH') Object.assign(session.row, { name: body.name, updatedAt: now(), version: session.row.version + 1 })
      else if (method === 'DELETE') {
        workspace.sessions = workspace.sessions.filter(s => s !== session)
        session = workspace.sessions[0]
      } else return unavailable()
    } else if (path === '/turns' && session && method === 'POST') {
      const turn = body as TurnInput
      if (entry.designType === 'custom' && turn.skillId) return json({ detail: '自定义生图不使用 Skill' }, 422)
      const assets = workspace.materials.filter(a => turn.attachmentIds.includes(a.id))
      appendTurn(session, turn.text, '本地预览已收到这条设计要求。', assets, turn.skillId ? skill.displayName : null)
    } else if (path === '/files' && options.body instanceof FormData) {
      const upload = options.body.get('file')
      if (!(upload instanceof File)) return unavailable()
      const id = token()
      const url = `${endpoint}/files/${id}/content`
      cacheThumbnail(url, upload)
      return json(addMaterial(workspace, `upload:${id}`, url, upload.name, upload))
    } else if (path.startsWith('/materials/') && method === 'DELETE') {
      const id = decodeURIComponent(path.slice('/materials/'.length))
      workspace.materials = workspace.materials.filter(a => a.id !== id)
    } else return unavailable()
    return json(snapshot(entry, workspace, session))
  }
  window.fetch = localFetch
  // Production attachment downloads use an anchor after the HEAD check. Deliver the local
  // file from a blob URL so clicking download never navigates to a business endpoint.
  function interceptDownload(event: MouseEvent) {
    const link = event.target instanceof Element ? event.target.closest('a[href]') : null
    if (!(link instanceof HTMLAnchorElement)) return
    const { pathname } = new URL(link.href)
    if (!pathname.startsWith('/api/')) return
    event.preventDefault()
    const file = workspace.files.get(pathname)
    if (!file) return
    const localUrl = URL.createObjectURL(file)
    const download = document.createElement('a')
    download.href = localUrl
    download.download = link.download
    download.click()
    window.setTimeout(() => URL.revokeObjectURL(localUrl), 30_000)
  }
  document.addEventListener('click', interceptDownload, true)
  return () => {
    document.removeEventListener('click', interceptDownload, true)
    thumbnails.forEach(url => URL.revokeObjectURL(url))
    thumbnails.clear()
    if (window.fetch === localFetch) window.fetch = nativeFetch
  }
}

