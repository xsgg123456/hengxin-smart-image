import type { Asset, StudioPicture } from '@/api/overseas/studio'
import { IdentityError } from '@/api/identity/request'

export type StudioImage = Asset | StudioPicture
export function isImage(asset: StudioImage) { return !('contentType' in asset) || ['image/jpeg', 'image/png', 'image/webp'].includes(asset.contentType) }
export function imageUrl(asset: StudioImage) { return 'contentType' in asset ? `${asset.url}?preview=true` : asset.url }
export async function checkImage(asset: StudioImage, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  const response = await fetcher(imageUrl(asset), { method: 'HEAD', credentials: 'include', cache: 'no-store', redirect: 'error', signal })
  if (!response.ok) throw new IdentityError(response.status, response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限读取图片' : '图片无法读取，请重试')
}
export async function loadStudioImage(picture: StudioPicture, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  const response = await fetcher(picture.url, { credentials: 'include', cache: 'no-store', redirect: 'error', signal })
  if (!response.ok) throw new IdentityError(response.status, response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限读取图片' : '原图加载失败，请重试')
  return response.blob()
}
