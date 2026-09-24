import type { Picture } from '@/types/hengxin'
import { ApiError, createRequest } from './http'

export interface RoundMaterialImage {
  role: string
  label: string
  picture: Picture | null
  version?: number | null
  reason?: string | null
}
export interface RoundMaterials {
  taskId: string
  roundId: string
  note: string
  status: string
  systemPrompts: { label: string; text: string }[]
  toolCalls: { label: string; prompt: string; images: string[] }[]
  inputs: RoundMaterialImage[]
  outputs: RoundMaterialImage[]
  notices: string[]
}
const record = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === 'string'
const texts = (value: unknown): value is string[] => Array.isArray(value) && value.every(text)
const version = (value: unknown) => value == null || (Number.isInteger(value) && Number(value) > 0)
function materialImage(value: unknown): value is RoundMaterialImage {
  if (
    !record(value) ||
    !text(value.role) ||
    !text(value.label) ||
    !version(value.version) ||
    (value.reason != null && !text(value.reason))
  )
    return false
  const picture = value.picture
  return (
    picture === null ||
    (record(picture) &&
      text(picture.name) &&
      text(picture.url) &&
      /^\/api\/v1\/(?:files|tasks)\//.test(picture.url) &&
      version(picture.version) &&
      (picture.fileId === undefined || text(picture.fileId)))
  )
}
export function isRoundMaterials(value: unknown): value is RoundMaterials {
  return (
    record(value) &&
    text(value.taskId) &&
    text(value.roundId) &&
    text(value.note) &&
    text(value.status) &&
    Array.isArray(value.systemPrompts) &&
    value.systemPrompts.every((p) => record(p) && text(p.label) && text(p.text)) &&
    Array.isArray(value.toolCalls) &&
    value.toolCalls.every(
      (p) =>
        record(p) &&
        text(p.label) &&
        text(p.prompt) &&
        texts(p.images) &&
        p.images.every((path) => path.startsWith('/work/')),
    ) &&
    Array.isArray(value.inputs) &&
    value.inputs.every(materialImage) &&
    Array.isArray(value.outputs) &&
    value.outputs.every(materialImage) &&
    texts(value.notices)
  )
}
export function createRoundMaterialsApi(baseUrl: string, fetcher: typeof fetch = fetch) {
  const request = createRequest(baseUrl, fetcher)
  return async (taskId: string, roundId: string) => {
    const data = await request(
      `/tasks/${encodeURIComponent(taskId)}/rounds/${encodeURIComponent(roundId)}/materials`,
      isRoundMaterials,
    )
    if (data.taskId !== taskId || data.roundId !== roundId)
      throw new ApiError('INVALID_RESPONSE', '执行材料与所选轮次不一致，请重新加载')
    return data
  }
}
