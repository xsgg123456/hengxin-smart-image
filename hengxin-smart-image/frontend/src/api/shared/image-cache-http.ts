import { IdentityError } from '../identity/request'

export const PREFETCH_IMAGE_BYTES = 32 * 1024 * 1024
export const cancelledImage = () => new DOMException('图片读取已取消', 'AbortError')
export function imageResponseError(status: number) {
  return new IdentityError(status, status === 401 ? '身份已失效，请重新登录' : status === 403 ? '暂无权限读取图片' : status === 404 ? '图片已不存在' : '原图加载失败，请重试')
}
export async function readImageBlob(response: Response, limit?: number) {
  if (!limit) return response.blob()
  if (Number(response.headers.get('Content-Length')) > limit) { await response.body?.cancel(); throw cancelledImage() }
  // A missing or dishonest Content-Length must not turn prefetch into an unbounded allocation.
  const reader = response.body?.getReader()
  if (!reader) return new Blob([], { type: response.headers.get('Content-Type') || '' })
  const chunks: Uint8Array[] = []; let size = 0
  try {
    while (true) {
      const part = await reader.read(); if (part.done) break
      size += part.value.byteLength
      if (size > limit) { await reader.cancel(); throw cancelledImage() }
      chunks.push(part.value)
    }
  } finally { reader.releaseLock() }
  return new Blob(chunks, { type: response.headers.get('Content-Type') || '' })
}
