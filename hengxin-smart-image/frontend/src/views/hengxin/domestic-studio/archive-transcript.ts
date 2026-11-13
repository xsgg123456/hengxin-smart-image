import type { ArchiveTurn } from '@/api/hengxin/domestic-archives'
import { mergeTranscript } from '@/views/shared/studio/studio-transcript'

export function archiveTranscript(turn: Pick<ArchiveTurn, 'id' | 'transcript'>) {
  return mergeTranscript([], (turn.transcript || []).map((item, index) => ({ ...item, id: index + 1,
    itemId: item.itemId ? `archive:${item.itemId}` : `legacy:${index}`, turnId: turn.id, createdAt: item.createdAt || '' })))
}
