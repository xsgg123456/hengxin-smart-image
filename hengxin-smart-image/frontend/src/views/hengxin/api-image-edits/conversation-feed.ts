import type { EditConversation, EditEvent } from '@/types/api-image-conversation'
/** A read begun before an SSE event cannot erase messages already displayed. */
export function acceptConversationSnapshot(current: EditConversation | undefined, incoming: EditConversation, cursor: number) {
  return incoming.lastEventId < Math.max(cursor, current?.lastEventId || 0) ? current : incoming
}
export function appendConversationEvent(current: EditConversation | undefined, event: EditEvent, cursor: number) {
  if (!current || event.id <= cursor || event.type !== 'message' || !event.text) return current
  return { ...current, lastEventId: event.id, turns: current.turns.map(turn => turn.id === event.turnId ? { ...turn, messages: [...turn.messages, event.text!] } : turn) }
}
