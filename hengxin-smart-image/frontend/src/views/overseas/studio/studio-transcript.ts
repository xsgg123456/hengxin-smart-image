import type { StudioTranscript } from '@/api/overseas/studio'

// The server appends snapshots. Replace an item in place, preserving its first appearance.
export function mergeTranscript(current: StudioTranscript[], incoming: StudioTranscript[]) {
  const result = [...current]
  const positions = new Map(result.map((item, index) => [JSON.stringify([item.turnId, item.itemId]), index]))
  for (const item of incoming) {
    const key = JSON.stringify([item.turnId, item.itemId]), index = positions.get(key)
    if (index === undefined) { positions.set(key, result.length); result.push(item) }
    else if (item.id > result[index].id) result[index] = item
  }
  return result
}
