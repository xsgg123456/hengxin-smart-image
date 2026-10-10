import { computed, onBeforeUnmount, ref, shallowRef } from 'vue'
import { imageConversations } from '@/api/api-image-conversation'
import { ApiError } from '@/api/hengxin/http'
import { identity } from '@/api/hengxin/identity'
import { errorText } from '@/api/api-image-edits'
import type { EditConversation, EditEvent } from '@/types/api-image-conversation'
import { isEditActive } from '@/types/api-image-conversation'
import { conversationCommand, type ConversationAction } from './conversation-command'
import { acceptConversationSnapshot, appendConversationEvent } from './conversation-feed'

export function useImageConversation(user: string, task: string, item: string) {
  const conversation = shallowRef<EditConversation>(), loading = ref(true), error = ref(''), connection = ref('正在连接'), command = conversationCommand(user, task, item)
  const active = computed(() => conversation.value?.turns.find(isEditActive))
  let alive = true, cursor = 0, revision = 0, refreshing: Promise<void> | undefined, refreshAgain = false
  const epoch = identity.epoch, controller = new AbortController()
  function apply(value: EditConversation) {
    if (!alive || !identity.current(epoch)) return
    // Late GET snapshots must never undo a newer mutation or stream snapshot.
    const accepted = acceptConversationSnapshot(conversation.value, value, cursor)
    if (accepted !== value) { refreshAgain = true; return }
    if (value.retention?.status === 'expired' && !(command.state.pending?.action.kind === 'submit' && command.state.pending.action.input.restartExpired)) command.discardExpired()
    conversation.value = value; cursor = Math.max(cursor, value.lastEventId)
  }
  async function refresh() {
    if (refreshing) { refreshAgain = true; return refreshing }
    refreshing = (async () => {
      do {
        refreshAgain = false
        try { const started = revision; const value = await imageConversations.get(task, item); if (started === revision) apply(value); else refreshAgain = true; if (alive) error.value = '' }
        catch (e) { if (alive) error.value = errorText(e) }
      } while (refreshAgain && alive)
    })().finally(() => { refreshing = undefined; if (alive) loading.value = false })
    return refreshing
  }
  function receive(event: EditEvent) {
    if (event.id <= cursor || !alive) return
    conversation.value = appendConversationEvent(conversation.value, event, cursor)
    cursor = event.id
    // State transitions also freeze candidate metadata; message events remain immediate.
    if (event.type === 'state') void refresh()
  }
  async function connect() {
    await refresh()
    while (alive && identity.current(epoch)) {
      try {
        connection.value = '实时连接中'
        await imageConversations.events(task, item, cursor, controller.signal, receive)
      } catch (e) {
        if (!alive || !identity.current(epoch)) return
        if (e instanceof ApiError && [401, 403, 404, 410].includes(e.status)) { error.value = errorText(e); connection.value = '连接已停止'; return }
      }
      if (!alive) return
      connection.value = '连接中断，正在恢复'
      await new Promise<void>(resolve => {
        const finish = () => { clearTimeout(timer); controller.signal.removeEventListener('abort', finish); resolve() }
        const timer = setTimeout(finish, 1500); controller.signal.addEventListener('abort', finish, { once: true })
      })
    }
  }
  const retentionPending = computed(() => ['cache_pending', 'expire_pending'].includes(conversation.value?.retention?.status || ''))
  async function send(action: ConversationAction) {
    if (loading.value || !conversation.value || retentionPending.value) return false
    if (conversation.value?.retention?.status === 'expired' && (action.kind !== 'submit' || !action.input.restartExpired || action.input.baseTurnId)) return false
    revision++
    const value = await command.send(action, (frozen, key) => frozen.kind === 'submit'
      ? imageConversations.submit(task, item, frozen.input, key)
      : imageConversations.adopt(task, item, frozen.turnId, frozen.expectedVersion, key))
    if (value) apply(value)
    return !!value && alive && identity.current(epoch)
  }
  async function stop() {
    if (!active.value || retentionPending.value) return
    revision++
    try { apply(await imageConversations.stop(task, item, active.value.id)) }
    catch (e) { if (alive) error.value = errorText(e) }
  }
  const unsubscribe = identity.subscribe(() => { alive = false; controller.abort(); conversation.value = undefined; error.value = '身份已变化，请重新打开修改'; connection.value = '连接已停止' })
  const polling = setInterval(() => { if (alive) void refresh() }, 15000)
  onBeforeUnmount(() => { clearInterval(polling); alive = false; controller.abort(); unsubscribe() })
  void connect()
  return { conversation, loading, error, connection, command, active, retentionPending, refresh, send, stop }
}
