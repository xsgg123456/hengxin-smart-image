import { ref, watch } from 'vue'
import { formatExecutionTime, stages, type ExecutionData } from '../../../api/hengxin/execution-data'

type ExecutionEvent = ExecutionData['events'][number]
export interface TimelineEntry extends ExecutionEvent { repeats: number; lastAt: string | null }
const isCodex = (event: ExecutionEvent) => event.message.startsWith('Codex：')

export function presentExecutionEvents(events: readonly ExecutionEvent[], expanded = false) {
  const broadcasts = events.filter(isCodex)
  const timeline: TimelineEntry[] = []
  for (const event of events.filter(event => !isCodex(event))) {
    const previous = timeline.at(-1)
    // Keep different stages and known/unknown time groups distinct; never invent history timestamps.
    if (previous && previous.stage === event.stage && previous.message === event.message &&
      (previous.at === null) === (event.at === null)) {
      previous.repeats++; previous.lastAt = event.at
    } else timeline.push({ ...event, repeats: 1, lastAt: event.at })
  }
  return { broadcasts: expanded ? broadcasts : broadcasts.slice(-3), total: broadcasts.length, timeline }
}

export function executionEventTime(event: ExecutionEvent) {
  return event.at === null ? (isCodex(event) ? '历史输出，未记录时间' : '未记录时间') : formatExecutionTime(event.at)
}

export function timelineDetail(event: ExecutionEvent) {
  return event.message.trim() === stages[event.stage] ? '' : event.message
}

interface DisplayContext {
  taskId: string; roundId: string; selected: string; currentRoundId?: string | null; identity: string; active: boolean
}
export function useExecutionDisclosure(context: () => DisplayContext) {
  const expanded = ref(false), timelineOpen = ref<string[]>([])
  watch(() => {
    const value = context()
    return [value.taskId, value.roundId, value.selected, value.currentRoundId, value.identity, value.active]
  }, () => { expanded.value = false; timelineOpen.value = [] }, { flush: 'sync' })
  return { expanded, timelineOpen }
}
