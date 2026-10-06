import { reactive } from 'vue'
import { errorText, uncertainResponse } from '@/api/api-image-edits'
import type { EditTurnInput } from '@/types/api-image-conversation'
export type ConversationAction = { kind: 'submit'; input: EditTurnInput } | { kind: 'adopt'; turnId: string; expectedVersion: number }
export interface PendingConversationAction { key: string; action: ConversationAction; uncertain: boolean }
export function createConversationCommand(storage?: { load(): PendingConversationAction | null; save(value: PendingConversationAction | null): void }, key = () => crypto.randomUUID()) {
  const state = reactive({ pending: storage?.load() || null as PendingConversationAction | null, busy: false, error: '' })
  async function send<T>(action: ConversationAction, request: (action: ConversationAction, key: string) => Promise<T>): Promise<T | undefined> {
    if (state.busy) return
    state.pending ||= { key: key(), action: structuredClone(action), uncertain: false }
    storage?.save(state.pending); state.busy = true; state.error = ''
    try {
      const result = await request(state.pending.action, state.pending.key)
      state.pending = null; storage?.save(null); return result
    } catch (error) {
      if (uncertainResponse(error)) state.pending!.uncertain = true
      else if (!state.pending?.uncertain) state.pending = null
      storage?.save(state.pending); state.error = errorText(error) + (state.pending ? '。请确认原请求，避免重复提交。' : '')
    } finally { state.busy = false }
  }
  return { state, send }
}
const commands = new Map<string, ReturnType<typeof createConversationCommand>>()
export function conversationCommand(user: string, task: string, item: string) {
  const id = `api-image-conversation:${user}:${task}:${item}`
  if (!commands.has(id)) commands.set(id, createConversationCommand({
    load() { try { const v = JSON.parse(sessionStorage.getItem(id) || 'null') as PendingConversationAction | null; return v?.key && ['submit', 'adopt'].includes(v.action?.kind) ? { ...v, uncertain: true } : null } catch { return null } },
    save(value) { try { if (value) sessionStorage.setItem(id, JSON.stringify(value)); else sessionStorage.removeItem(id) } catch { /* 内存保留冻结请求 */ } }
  }))
  return commands.get(id)!
}
