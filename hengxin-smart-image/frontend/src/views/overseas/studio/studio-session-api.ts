import type { Studio, StudioApi, StudioConversation } from '@/api/overseas/studio'

// Every controller shares this ordering boundary. Task versions alone do not
// change when a conversation is created, renamed or starts a turn.
export class ObsoleteStudioSnapshot extends Error {}
export function sessionOrderedApi(api: StudioApi): StudioApi & { currentSnapshot: (value: Studio) => Studio } {
  let epoch = 0, writes = 0, sequence = 0, acceptedRead = 0
  let rows: StudioConversation[] | undefined
  let task: Pick<Studio, 'taskVersion' | 'completed' | 'reopened' | 'archiveId'> | undefined
  function reconcile(value: Studio, full: boolean, target?: string | null): Studio {
    if (!task || value.taskVersion > task.taskVersion) {
      task = { taskVersion: value.taskVersion, completed: value.completed, reopened: value.reopened, archiveId: value.archiveId }
    } else if (value.taskVersion === task.taskVersion && (full || value.archiveId)) task.archiveId = value.archiveId
    if (value.conversations) {
      if (full || !rows) rows = value.conversations
      else if (target) {
        const incoming = value.conversations.find(row => row.id === target)
        const previous = rows.find(row => row.id === target)
        if (incoming && (!previous || incoming.version >= previous.version)) {
          rows = previous ? rows.map(row => row.id === target ? incoming : row) : [...rows, incoming]
        }
      }
    }
    return currentSnapshot(value)
  }
  function currentSnapshot(value: Studio): Studio {
    return { ...value, ...task, conversations: rows, activeConversationCount: rows?.filter(row => !!row.activeTurnId).length ?? value.activeConversationCount }
  }
  async function mutate(call: () => Promise<Studio>, target?: string): Promise<Studio> {
    ++epoch; ++writes
    try {
      const value = await call()
      // A receipt acknowledges its own operation. Its other conversation rows
      // may predate concurrently completed writes and must never replace them.
      return reconcile(value, false, target || value.conversationId)
    } finally { --writes; ++epoch }
  }
  return {
    ...api,
    currentSnapshot,
    async get(...args) {
      for (let attempt = 0; attempt < 3; attempt++) {
        args[1]?.throwIfAborted()
        const started = epoch, order = ++sequence, stable = writes === 0
        let value: Studio
        try { value = await api.get(...args) }
        catch (reason) {
          // A late 404 is not evidence that the current selection was deleted.
          if (started !== epoch || order < acceptedRead) continue
          throw reason
        }
        args[1]?.throwIfAborted()
        if (started !== epoch || order < acceptedRead || (task && value.taskVersion < task.taskVersion)) continue
        acceptedRead = order
        // Reads still initialize B while A's POST is pending; no write is queued
        // behind another session. Only a stable read can remove list entries.
        return reconcile(value, stable && writes === 0)
      }
      throw new ObsoleteStudioSnapshot('等待最新会话状态')
    },
    send: (...args) => mutate(() => api.send(...args), args[1].conversationId || args[3]),
    newConversation: (...args) => mutate(() => api.newConversation(...args)),
    renameConversation: (...args) => mutate(() => api.renameConversation(...args), args[1]),
    deleteConversation: (...args) => mutate(() => api.deleteConversation(...args), args[1]),
    cancel: (...args) => mutate(() => api.cancel(...args), args[1].conversationId),
    archive: (...args) => mutate(() => api.archive(...args), args[4]),
    complete: (...args) => mutate(() => api.complete(...args)),
    reopen: (...args) => mutate(() => api.reopen(...args)),
    removeMaterial: (...args) => mutate(() => api.removeMaterial(...args), args[2]),
    async upload(...args) {
      ++epoch; ++writes
      try { return await api.upload(...args) } finally { --writes; ++epoch }
    }
  }
}
