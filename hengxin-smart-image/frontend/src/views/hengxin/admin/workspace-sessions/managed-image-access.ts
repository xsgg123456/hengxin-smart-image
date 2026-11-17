import { readManagedAsset } from '@/api/hengxin/workspace-sessions'
import type { StudioImage, StudioImageAccess } from '@/views/shared/studio/studio-images'

async function load(asset: StudioImage, signal: AbortSignal, thumbnail = false) {
  const blob = await readManagedAsset(asset.url, signal, fetch, thumbnail)
  signal.throwIfAborted()
  const url = URL.createObjectURL(blob)
  return { blob, url, release: () => URL.revokeObjectURL(url) }
}
export async function downloadManagedAsset(asset: StudioImage, signal: AbortSignal) {
  const lease = await load(asset, signal), link = document.createElement('a')
  link.href = lease.url; link.download = asset.name; document.body.appendChild(link)
  try { link.click() } finally {
    link.remove()
    // Let the browser consume the download URL before releasing it.
    setTimeout(lease.release, 1000)
  }
}
export const managedImageAccess: StudioImageAccess = {
  load,
  thumbnail: (asset, signal) => load(asset, signal, true),
  download: downloadManagedAsset
}
