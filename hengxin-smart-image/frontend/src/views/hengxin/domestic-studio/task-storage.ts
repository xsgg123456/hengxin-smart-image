import { isDomesticAsset, type Studio } from '@/api/shared/studio'
import { composerDraftKey } from '@/views/shared/studio/studio-composer-draft'
import { pendingKey, pendingOwner, type Pending } from '@/views/shared/studio/studio-pending'
import { record } from '@/api/identity/request'

/** Only server-confirmed conversation ownership permits moving an old workspace draft. */
export function restoreTaskStorage(actor: string, workspace: string, value: Studio) {
  for (const session of value.conversations || []) {
    const oldKey = composerDraftKey(actor, workspace, session.id), nextKey = composerDraftKey(actor, value.taskId, session.id)
    const raw = localStorage.getItem(oldKey)
    if (raw && !localStorage.getItem(nextKey)) {
      const draft: unknown = JSON.parse(raw)
      if (record(draft) && Array.isArray(draft.attachments) && draft.attachments.every(asset => isDomesticAsset(asset, workspace))) {
        const attachments = draft.attachments.map(asset => ({ ...asset, url: `/api/v1/domestic-studio/tasks/${encodeURIComponent(value.taskId)}/studio/files/${encodeURIComponent(asset.id.slice(7))}/content` }))
        localStorage.setItem(nextKey, JSON.stringify({ ...draft, attachments }))
        localStorage.removeItem(oldKey)
      }
    }
    for (const source of [pendingKey(actor, workspace, session.id), pendingKey(actor, workspace)]) {
      const saved = sessionStorage.getItem(source)
      if (!saved) continue
      const pending = JSON.parse(saved) as Pending
      if (!pending.key || pendingOwner(pending) !== session.id) continue
      const target = pendingKey(actor, value.taskId, session.id)
      if (!sessionStorage.getItem(target)) {
        sessionStorage.setItem(target, saved)
        sessionStorage.removeItem(source)
      }
    }
  }
}
