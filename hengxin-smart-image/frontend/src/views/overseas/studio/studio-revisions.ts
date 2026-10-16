import type { Asset, StudioPicture } from '@/api/overseas/studio'
export interface StudioRevision { base: StudioPicture; annotation?: Asset; text: string; draftKey: string }
export function studioDraftKey(actor: string, task: string, conversation: string | null | undefined, picture: string) {
  return `studio-annotation:${JSON.stringify([actor, task, conversation || '', picture])}`
}
