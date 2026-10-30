import type { Asset, StudioPicture } from '@/api/overseas/studio'
import { IdentityError } from '@/api/identity/request'
import { createImageCache, overseasImageCache } from '@/api/overseas/image-cache'

export type StudioImage = Asset | StudioPicture
export function isImage(asset: StudioImage) { return !('contentType' in asset) || ['image/jpeg', 'image/png', 'image/webp'].includes(asset.contentType) }
export function imageUrl(asset: StudioImage) { return 'contentType' in asset ? `${asset.url}?preview=true` : asset.url }
export function thumbnailUrl(asset: StudioImage) { const url = imageUrl(asset); return `${url}${url.includes('?') ? '&' : '?'}thumbnail=true` }
export async function checkImage(asset: StudioImage, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  const response = await fetcher(imageUrl(asset), { method: 'HEAD', credentials: 'include', cache: 'no-store', redirect: 'error', signal })
  if (!response.ok) {
    if ([401, 403, 404].includes(response.status)) overseasImageCache.invalidate(imageUrl(asset))
    throw new IdentityError(response.status, response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限读取图片' : '图片无法读取，请重试')
  }
}
export async function loadStudioImage(picture: StudioPicture, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  const cache = fetcher === fetch ? overseasImageCache : createImageCache({ fetcher })
  if (fetcher !== fetch) cache.setIdentity('isolated-reader')
  const lease = await cache.acquire(picture.url, { signal })
  try { return lease.blob } finally { lease.release() }
}
