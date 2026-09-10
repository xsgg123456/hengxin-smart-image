export function safeFilename(name: string, extension: string): string {
  const base = name.replace(/[/\\<>:"|?*\u0000-\u001f]/g, '_').replace(/(?:\.(?:png|jpe?g|webp|gif|svg|avif|zip))+$/i, '').replace(/[. ]+$/g, '').slice(0, 120)
  const safe = !base || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(base) ? `图片_${base}` : base
  return `${safe}.${extension}`
}
export async function readImage(url: string, timeoutMs = 15000): Promise<{ data: Uint8Array; extension: string; mime: string }> {
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, { signal: controller.signal, credentials: 'same-origin' })
    if (!response.ok) throw new Error('图片请求失败')
    const blob = await response.blob(), data = new Uint8Array(await blob.arrayBuffer())
    const mime = blob.type.split(';')[0].trim().toLowerCase()
    const extension = imageExtension(data, mime)
    return { data, extension, mime }
  } finally { clearTimeout(timeout) }
}
export function imageExtension(data: Uint8Array, mime: string): string {
  const starts = (...bytes: number[]) => bytes.every((byte, i) => data[i] === byte)
  const ascii = (start: number, end: number) => new TextDecoder().decode(data.slice(start, end))
  if (mime === 'image/png' && data.length >= 24 && starts(137, 80, 78, 71, 13, 10, 26, 10) && ascii(12, 16) === 'IHDR') return 'png'
  if (mime === 'image/jpeg' && data.length >= 4 && starts(255, 216, 255) && data.some((byte, index) => index >= 2 && byte === 255 && data[index + 1] === 217)) return 'jpg'
  if (mime === 'image/webp' && data.length >= 20 && ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP' && ['VP8 ', 'VP8L', 'VP8X'].includes(ascii(12, 16))) return 'webp'
  if (mime === 'image/gif' && data.length >= 14 && ['GIF87a', 'GIF89a'].includes(ascii(0, 6)) && data.at(-1) === 59) return 'gif'
  if (mime === 'image/svg+xml') {
    const text = new TextDecoder().decode(data).trim().replace(/^<\?xml[^?]*\?>\s*/i, '')
    if (/^<svg(?:\s|>)/i.test(text) && /(?:<\/svg>|\/>)\s*$/i.test(text) && !/<(?:html|script)(?:\s|>)/i.test(text)) return 'svg'
  }
  throw new Error('文件不是有效的受支持图片，请重试')
}
export function crc32(bytes: Uint8Array) {
  let crc = -1
  for (const b of bytes) { crc ^= b; for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0) }
  return (crc ^ -1) >>> 0
}
export function buildZip(files: { name: string; data: Uint8Array }[]): Blob {
  if (!files.length || files.length > 65535) throw new Error('没有可打包的图片或图片过多')
  const parts: Uint8Array[] = [], directory: Uint8Array[] = []
  let offset = 0
  for (const file of files) {
    const filename = new TextEncoder().encode(file.name), data = file.data, crc = crc32(data)
    if (!data.length || filename.length > 65535 || offset + data.length + filename.length + 30 > 0xffffffff) throw new Error('图片为空或超过打包限制')
    const h = new Uint8Array(30 + filename.length), v = new DataView(h.buffer)
    v.setUint32(0, 0x04034b50, true); v.setUint16(4, 20, true); v.setUint16(6, 0x800, true)
    v.setUint32(14, crc, true); v.setUint32(18, data.length, true); v.setUint32(22, data.length, true); v.setUint16(26, filename.length, true); h.set(filename, 30)
    const c = new Uint8Array(46 + filename.length), d = new DataView(c.buffer)
    d.setUint32(0, 0x02014b50, true); d.setUint16(4, 20, true); d.setUint16(6, 20, true); d.setUint16(8, 0x800, true)
    d.setUint32(16, crc, true); d.setUint32(20, data.length, true); d.setUint32(24, data.length, true); d.setUint16(28, filename.length, true); d.setUint32(42, offset, true); c.set(filename, 46)
    parts.push(h, data); directory.push(c); offset += h.length + data.length
  }
  const end = new Uint8Array(22), e = new DataView(end.buffer), directorySize = directory.reduce((n, p) => n + p.length, 0)
  if (offset + directorySize > 0xffffffff) throw new Error('超过打包限制')
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, directorySize, true); e.setUint32(16, offset, true)
  return new Blob([...parts, ...directory, end], { type: 'application/zip' })
}
export async function prepareSet(images: { name: string; url: string }[]): Promise<Blob> {
  if (!images.length) throw new Error('没有可下载图片')
  const files = []
  for (const [index, image] of images.entries()) {
    const { data, extension } = await readImage(image.url)
    files.push({ name: `${String(index + 1).padStart(2, '0')}-${safeFilename(image.name, extension)}`, data })
  }
  return buildZip(files)
}

export async function requestDownload(baseUrl: string, fileIds: (string | undefined)[], name?: string): Promise<Blob> {
  if (!fileIds.length || fileIds.length > 20 || fileIds.some(id => !id || !/^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(id))) {
    throw new Error('图片文件标识缺失或无效，请刷新后重试')
  }
  const zipped = name !== undefined
  const path = zipped ? '/files/download-zip' : `/files/${fileIds[0]}/content?download=true`
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
    method: zipped ? 'POST' : 'GET', credentials: 'include', signal: AbortSignal.timeout(300000),
    headers: zipped ? { 'Content-Type': 'application/json', Accept: 'application/zip' } : { Accept: 'image/*' },
    body: zipped ? JSON.stringify({ fileIds, name }) : undefined
  })
  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('hengxin:unauthorized'))
    let message = `下载请求失败（${response.status}）`
    try {
      const error: unknown = await response.json()
      if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') message = error.message
    } catch { /* 网关非 JSON 错误使用状态提示 */ }
    throw new Error(message)
  }
  const blob = await response.blob()
  if (zipped) {
    if (blob.type.split(';')[0] !== 'application/zip' || blob.size < 22) throw new Error('打包响应无效，请重试')
    const end = new DataView(await blob.slice(-22).arrayBuffer())
    if (end.getUint32(0, true) !== 0x06054b50 || end.getUint16(10, true) !== fileIds.length) throw new Error('打包结果不完整，请重试')
  } else {
    imageExtension(new Uint8Array(await blob.arrayBuffer()), blob.type.split(';')[0])
  }
  return blob
}
