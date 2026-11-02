import type { StudioPicture } from './studio'
import { overseasImageCache } from './image-cache'
import { buildZip, imageExtension, safeFilename } from '../../views/hengxin/download-helpers'

export async function prepareStudioDownload(pictures: Pick<StudioPicture, 'id' | 'name' | 'url'>[], signal: AbortSignal, cache = overseasImageCache) {
  if (!pictures.length) throw Error('请选择要下载的图片')
  const files = []
  for (const [index, picture] of pictures.entries()) {
    signal.throwIfAborted()
    if (!/^\/api\/overseas\/v1\/tasks\/[a-zA-Z0-9-]+\/studio\/pictures\/[a-zA-Z0-9-]+\/content$/.test(picture.url)) throw Error('图片地址无效')
    const lease = await cache.acquire(picture.url, { signal })
    try {
      const data = new Uint8Array(await lease.blob.arrayBuffer())
      signal.throwIfAborted()
      const extension = imageExtension(data, lease.blob.type.split(';')[0].trim().toLowerCase())
      files.push({ name: `${String(index + 1).padStart(3, '0')}_${safeFilename(picture.name, extension)}`, data })
    } finally { lease.release() }
  }
  signal.throwIfAborted()
  return buildZip(files)
}
