import type { ApiPicture } from '@/types/api-image-edits'

export interface RevisionReference { picture: ApiPicture; name: string; role: string }
export function revisionReferences(kind: 'image_edit' | 'text_edit', current?: ApiPicture | null, original?: ApiPicture | null, material?: ApiPicture | null): RevisionReference[] {
  const inputs = [{ picture: current, name: '当前成品', role: '本次唯一编辑底图' }]
  if (kind === 'image_edit') inputs.push(
    { picture: original, name: '对应原图', role: '仅参考指定修改的构图与空间关系' },
    { picture: material, name: '共用素材', role: '仅参考指定对象的外观与细节' }
  )
  return inputs.map(input => {
    if (!input.picture?.fileId || !input.picture.url) throw new Error(`${input.name}不可用，请重新读取任务详情后再修改。`)
    return { ...input, picture: { ...input.picture } }
  })
}
