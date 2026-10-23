import { createRenderer, defineComponent, nextTick } from 'vue'
import { emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import type { Studio, StudioApi, StudioConversation, UploadedAsset } from '../src/api/overseas/studio'
import { useStudioSessions } from '../src/views/overseas/studio/use-studio-sessions'
export const local = new Map<string, string>(), session = new Map<string, string>()
for (const [name, store] of [['localStorage', local], ['sessionStorage', session]] as const) Object.defineProperty(globalThis, name, { configurable: true, value: {
  getItem: (key: string) => store.get(key) || null, setItem: (key: string, value: string) => store.set(key, value), removeItem: (key: string) => store.delete(key)
} })
const renderer = createRenderer<object, object>({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}, setText() {}, setElementText() {} })
export const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); await nextTick() }
export const asset = (id: string): UploadedAsset => ({ id: `upload:${id}`, name: `${id}.txt`, source: 'upload', contentType: 'text/plain', sizeBytes: 1, url: `/api/overseas/v1/tasks/t/studio/files/${id}/content` })
export const row = (id: string): StudioConversation => ({ id, name: `会话${id}`, version: 1, createdAt: '2026-10-24T01:00:00Z', updatedAt: '2026-10-24T01:00:00Z', activeTurnId: null, status: 'empty', turnCount: 0 })
export function fixture() {
  local.clear(); session.clear()
  const rows = [row('a'), row('b')], calls: { kind: string; id?: string; body?: unknown; key?: string }[] = []
  let version = 1, completed = false, archiveId: string | null = null
  const snapshot = (id = rows[0]?.id || ''): Studio => ({ taskId: 't', taskVersion: version, archiveId, completed, reopened: version > 1 && !completed,
    conversationId: id || null, conversations: structuredClone(rows), activeConversationCount: rows.filter(r => !!r.activeTurnId).length, maxConversations: 10,
    materials: [asset(id)], skills: [{ id: 's', name: 'skill', displayName: '测试Skill', description: '' }], turns: [], activeTurnId: rows.find(r => r.id === id)?.activeTurnId || null })
  const api: StudioApi = {
    get: async (_task, _signal, id) => { calls.push({ kind: 'get', id }); return snapshot(id) },
    transcript: async (_task, _after, _signal, id) => { calls.push({ kind: 'transcript', id }); return { items: [], cursor: 0, hasMore: false } },
    events: async () => ({ items: [], cursor: 0 }),
    send: async (_task, body, key) => { calls.push({ kind: 'send', id: body.conversationId, body, key }); return snapshot(body.conversationId) },
    upload: async (_task, _file, _signal, id) => { calls.push({ kind: 'upload', id }); return asset(`${id}-new`) },
    removeMaterial: async (_task, _asset, id) => { calls.push({ kind: 'remove', id }); return snapshot(id) },
    newConversation: async (_task, key) => { calls.push({ kind: 'create', key }); rows.push(row(`n${rows.length}`)); return snapshot(rows.at(-1)!.id) },
    renameConversation: async (_task, id, name, _version, key) => { calls.push({ kind: 'rename', id, key }); rows.find(r => r.id === id)!.name = name; return snapshot(id) },
    deleteConversation: async (_task, id, _version, key) => { calls.push({ kind: 'delete', id, key }); rows.find(r => r.id === id)!.deletionStatus = 'deleting'; return snapshot(id) },
    cancel: async (_task, turn) => { calls.push({ kind: 'cancel', id: turn.conversationId }); return snapshot(turn.conversationId) },
    archive: async (_task, _pictures, _sku, _key, id) => { archiveId = 'archive'; return snapshot(id) },
    complete: async () => { version++; completed = true; return snapshot() }, reopen: async () => { version++; completed = false; return snapshot() }
  }
  function mount(actor = 'designer', caps = ['task.design']) {
    const task = { ...emptyTaskDraft(), id: 't', version: 1, capabilities: caps } as TaskDetail
    let state!: ReturnType<typeof useStudioSessions>
    const failures: unknown[] = []
    const app = renderer.createApp(defineComponent({ setup() { state = useStudioSessions(() => task, e => failures.push(e), () => {}, api, actor); return () => null } })); app.mount({})
    return { state, failures, close: () => app.unmount() }
  }
  return { api, rows, snapshot, calls, mount }
}
export function deferred<T>() { let resolve!: (value: T) => void, reject!: (reason: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
