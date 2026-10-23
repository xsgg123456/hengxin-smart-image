import { ref, type Ref } from 'vue'
import type { StudioConversation, TurnInput } from '@/api/overseas/studio'

export type Pending = ({ key: string; kind: 'send'; body: TurnInput; draftKeys?: string[] }
  | { key: string; kind: 'archive'; body: { pictureIds: string[]; sku: string; conversationId?: string } }
  | { key: string; kind: 'complete' | 'reopen'; body: { version: number } }
  | { key: string; kind: 'conversation' }) & { draftConversationId?: string | null; legacy?: boolean }

export const pendingKey = (actor: string, task: string, id?: string) => `hx-studio-pending:${actor}:${task}${id ? `:${id}` : ''}`
export function pendingOwner(value: Pending) {
  const bodyId = (value.kind === 'send' || value.kind === 'archive') ? value.body?.conversationId : undefined
  if (bodyId && value.draftConversationId && bodyId !== value.draftConversationId) return undefined
  return bodyId || value.draftConversationId || undefined
}

// The old global slot has no relationship to the server's default/latest session.
// Keep it intact until its original owner is proven and a nonconflicting slot exists.
export function legacyPending(actor: string, task: string, notice: Ref<string>) {
  const unresolved = ref(false), globalKey = pendingKey(actor, task)
  function recover(rows: StudioConversation[]) {
    try {
      const raw = sessionStorage.getItem(globalKey)
      if (!raw) { unresolved.value = false; return }
      unresolved.value = true
      const value = JSON.parse(raw) as Pending, id = pendingOwner(value)
      if (!value.key || !id || !rows.some(row => row.id === id && !row.deletionStatus)) {
        notice.value = '旧版待核实请求及原文已保留，原会话缺失、已删除或无法确认；请核实历史记录，勿重新发送。'
        return
      }
      const target = pendingKey(actor, task, id), occupied = sessionStorage.getItem(target)
      if (occupied && JSON.parse(occupied).key !== value.key) {
        notice.value = '原会话已有另一条待核实请求；旧版请求及原文已保留，请先核实两条请求。'
        return
      }
      sessionStorage.setItem(target, JSON.stringify({ ...value, legacy: true }))
      sessionStorage.removeItem(globalKey)
      unresolved.value = false
      notice.value = '旧版待核实请求已恢复到原会话，请切换到该会话核实；其他会话草稿保持不变。'
      return { id, value: { ...value, legacy: true } }
    } catch {
      unresolved.value = true
      notice.value = '旧版待核实请求无法安全恢复，原记录已保留，请检查浏览器存储并核实历史记录。'
    }
  }
  return { recover, unresolved }
}
