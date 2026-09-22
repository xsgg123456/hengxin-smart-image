import { reactive } from 'vue'
import { errorText, uncertainResponse } from '@/api/api-image-edits'
import type { ApiPicture, ApiRevisionInput } from '@/types/api-image-edits'
export type ItemCommand = { kind: 'revise'; input: ApiRevisionInput; annotation?: ApiPicture } | { kind: 'restore'; version: number } | { kind: 'retry' }
export interface PendingCommand { key: string; command: ItemCommand; uncertain: boolean }
export interface CommandStorage { load(): PendingCommand | null; save(value: PendingCommand | null): void }
export function createItemCommand(storage?: CommandStorage, key = () => crypto.randomUUID()) {
  const state = reactive({ pending: storage?.load() || null as PendingCommand | null, busy: false, error: '' })
  async function submit(command: ItemCommand, send: (command: ItemCommand, key: string) => Promise<unknown>) {
    if (state.busy) return false
    state.pending ||= { key: key(), command: JSON.parse(JSON.stringify(command)) as ItemCommand, uncertain: false }
    storage?.save(state.pending); state.busy = true; state.error = ''
    try {
      await send(state.pending.command, state.pending.key)
      state.pending = null; storage?.save(null)
      return true
    } catch (error) {
      if (uncertainResponse(error)) state.pending!.uncertain = true
      else if (!state.pending?.uncertain) state.pending = null
      storage?.save(state.pending)
      state.error = errorText(error) + (state.pending ? '。受理结果尚未确认，请确认原请求；输入已锁定。' : '')
      return false
    } finally { state.busy = false }
  }
  return { state, submit }
}
const commands = new Map<string, ReturnType<typeof createItemCommand>>()
export function itemCommand(user: string, task: string, item: string) {
  const id = `api-image-command:${user}:${task}:${item}`
  if (!commands.has(id)) commands.set(id, createItemCommand({
    load() { try { const value = JSON.parse(sessionStorage.getItem(id) || 'null') as PendingCommand | null; return value?.key && ['revise', 'restore', 'retry'].includes(value.command?.kind) ? { ...value, uncertain: true } : null } catch { return null } },
    save(value) { try { if (value) sessionStorage.setItem(id, JSON.stringify(value)); else sessionStorage.removeItem(id) } catch { /* 内存仍保留原请求 */ } }
  }))
  return commands.get(id)!
}
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = name; document.body.append(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
export const friendlyTime = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) }
