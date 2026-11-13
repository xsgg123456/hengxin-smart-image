import type { Asset, EditReference, StudioPicture, StudioTurn } from '@/api/shared/studio'
import type { AnnotationMark } from '@/views/hengxin/components/annotation/annotation-model'
export interface RevisionReference extends Omit<EditReference, 'attachmentId'> { asset: Asset }
export interface StudioRevision { base: StudioPicture; annotation?: Asset; text: string; draftKey: string; referenceImages?: RevisionReference[]; marks?: AnnotationMark[] }
export function revisionAssetIds(revision: StudioRevision) {
  return [...(revision.annotation ? [revision.annotation.id] : []), ...(revision.referenceImages || []).map(r => r.asset.id)]
}
export function historicalRevisions(turn: Pick<StudioTurn, 'imageEdits' | 'referencePictures' | 'attachments'>): StudioRevision[] {
  return (turn.imageEdits || []).flatMap(edit => {
    const base = turn.referencePictures.find(p => p.id === edit.pictureId)
    if (!base) return []
    return [{ base, annotation: turn.attachments.find(a => a.id === edit.annotationId), text: edit.text, draftKey: '',
      referenceImages: (edit.references || []).flatMap(r => {
        const asset = turn.attachments.find(a => a.id === r.attachmentId)
        return asset ? [{ asset, kind: r.kind, customPurpose: r.customPurpose, note: r.note }] : []
      }) }]
  })
}
export function studioDraftKey(actor: string, task: string, conversation: string | null | undefined, picture: string) {
  return `studio-annotation:${JSON.stringify([actor, task, conversation || '', picture])}`
}
