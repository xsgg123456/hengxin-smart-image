import { forgetAnnotationDraft } from '../components/annotation/annotation-drafts'
const records = new Map<string, { epoch: string; keys: Set<string> }>()
export function conversationDrafts(id: string) {
  let record = records.get(id)
  if (!record) { record = { epoch: '', keys: new Set() }; records.set(id, record) }
  return {
    epoch: () => record.epoch,
    track(key: string) { record.keys.add(key) },
    expire(epoch: string) {
      if (record.epoch === epoch) return
      for (const key of record.keys) forgetAnnotationDraft(key)
      record.keys.clear(); record.epoch = epoch
    }
  }
}
