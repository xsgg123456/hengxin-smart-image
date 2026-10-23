import { computed, isRef, type Ref } from 'vue'
import type { StudioConversation } from '@/api/overseas/studio'
import { useStudio } from './use-studio'
export type StudioController = ReturnType<typeof useStudio>
export interface SessionView extends StudioConversation { unread: boolean; draft: boolean }
export const completionStamp = (s: StudioConversation) => `${s.turnCount}:${s.status}`
export const sessionRunning = (s: StudioConversation) => !!s.activeTurnId
export function sessionLabel(s: SessionView) {
  if (s.deletionStatus === 'deleting') return '删除中'
  if (s.deletionStatus === 'delete_failed') return '删除失败 · 可重试'
  if (s.status === 'queued') return '排队中'
  if (s.activeTurnId) return '生成中'
  if (s.unread) return s.status === 'failed' ? '执行失败 · 未读' : '有新结果'
  return ({ empty: '待开始', succeeded: '已完成', failed: '执行失败', cancelled: '已停止' } as Record<string, string>)[s.status] || s.status
}
// References and methods always resolve against the selected controller. In-flight methods
// retain their original controller closure, so their responses cannot touch another draft.
export function forwardController(current: Ref<StudioController>): StudioController {
  const output: Record<string, unknown> = {}
  const entries = current.value as unknown as Record<string, unknown>
  for (const key of Object.keys(entries)) {
    if (isRef(entries[key])) output[key] = computed({
      get: () => (current.value[key as keyof StudioController] as Ref<unknown>).value,
      set: value => { (current.value[key as keyof StudioController] as Ref<unknown>).value = value }
    })
    else if (typeof entries[key] === 'function') output[key] = (...args: unknown[]) =>
      (current.value[key as keyof StudioController] as (...values: unknown[]) => unknown)(...args)
    else output[key] = entries[key]
  }
  return output as StudioController
}
export const sessionPreferenceKey = (actor: string, task: string) => `hx-studio-sessions:${JSON.stringify([actor, task])}`
