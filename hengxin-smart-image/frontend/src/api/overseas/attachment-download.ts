import { IdentityError } from '../identity/request'

export function formatAttachmentSize(bytes: number) {
  if (bytes < 1000) return `${bytes} B`
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} KB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}

export async function downloadAttachment(url: string, name: string, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  // Only our two attachment routes are downloadable here; generated images have their own UI.
  if (!/^\/api\/overseas\/v1\/(?:materials\/[a-zA-Z0-9-]+|tasks\/[a-zA-Z0-9-]+\/studio\/files\/[a-zA-Z0-9-]+)\/content$/.test(url)) throw Error('附件地址无效')
  const deadline = AbortSignal.timeout(10000), combined = AbortSignal.any([signal, deadline])
  let response: Response
  try {
    combined.throwIfAborted()
    response = await fetcher(url, { method: 'HEAD', credentials: 'include', cache: 'no-store', redirect: 'error', headers: { 'X-HX-Request': '1' }, signal: combined })
    combined.throwIfAborted()
  } catch {
    if (signal.aborted) throw Error('下载检查已取消')
    throw Error(deadline.aborted ? '下载检查超时，请重试' : '附件服务连接失败，请重试')
  }
  if (!response.ok) throw new IdentityError(response.status, response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限下载此附件' : response.status === 404 ? '附件不存在或已不可访问' : '附件暂时无法下载，请重试')
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  document.body.appendChild(anchor)
  try { anchor.click() } finally { anchor.remove() }
}
