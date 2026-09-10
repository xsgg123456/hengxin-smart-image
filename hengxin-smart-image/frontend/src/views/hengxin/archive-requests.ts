import type { Archive } from '../../types/hengxin'

type Submit = (taskId: string, versionIds: string[], key: string) => Promise<Archive>
interface Pending { versionIds: string[]; key: string }

export function createArchiveRequests() {
  const pending = new Map<string, Pending>()
  return async (owner: string, taskId: string, versionIds: string[], send: Submit) => {
    const scope = JSON.stringify([owner, taskId])
    const action = pending.get(scope) ?? { versionIds: [...versionIds], key: crypto.randomUUID() }
    pending.set(scope, action)
    try {
      const archive = await send(taskId, [...action.versionIds], action.key)
      pending.delete(scope)
      return archive
    } catch (reason) {
      // A lost response must replay its original versions even after the detail refreshed.
      const status = reason && typeof reason === 'object' && 'status' in reason ? reason.status : 0
      if (typeof status === 'number' && [403, 404, 409, 422].includes(status)) pending.delete(scope)
      throw reason
    }
  }
}

export const submitArchive = createArchiveRequests()
