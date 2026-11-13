import { reactive, ref } from 'vue'
import { workspaces, type WorkspaceId } from './workspaces'
export type Asset = { id: number; name: string; url: string; image: boolean; role: string }
// Explicit preview identity; production must use the authenticated actor snapshot on each message.
export const previewActor = { id: 'preview-user', name: '演示用户' }
export type Message = { id: number; role: 'user' | 'assistant'; text: string; createdAt: string; actorName?: string; actorId?: string; skill?: { id: string; name: string }; status?: 'replied' | 'stopped'; files?: Asset[] }
export type Conversation = { id: number; name: string; renamed: boolean; running: boolean; draft: string; assets: Asset[]; pending: Asset[]; messages: Message[] }
export const createConversation = (name = '新会话 1'): Conversation => ({ id: Date.now() + Math.random(), name, renamed: false, running: false, draft: '', assets: [], pending: [], messages: [] })
export const states = reactive(Object.fromEntries(workspaces.map(item => [item.id, { conversations: [createConversation()], active: 0, nextSerial: 2 }])) as Record<WorkspaceId, { conversations: Conversation[]; active: number; nextSerial: number }>)
const timers = new Map<number, ReturnType<typeof setTimeout>>()
export function startDemoReply(conversation: Conversation, text: string) {
  if (conversation.running) return
  conversation.running = true
  timers.set(conversation.id, setTimeout(() => {
    conversation.messages.push({ id: Date.now(), role: 'assistant', text, createdAt: new Date().toISOString(), status: 'replied' })
    conversation.running = false
    timers.delete(conversation.id)
  }, 1800))
}
export function stopDemoReply(conversation: Conversation) {
  const timer = timers.get(conversation.id)
  if (timer) clearTimeout(timer)
  timers.delete(conversation.id)
  if (conversation.running) conversation.messages.push({ id: Date.now(), role: 'assistant', createdAt: new Date().toISOString(), status: 'stopped', text: '本轮演示已停止，可以继续补充要求。' })
  conversation.running = false
}
// Keep the help panel open when switching business entries, with content following the route.
export const tutorialOpen = ref(false)
