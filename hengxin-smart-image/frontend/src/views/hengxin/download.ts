import type { Picture } from './model'
import { ElMessage } from 'element-plus'
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a')
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000)
}
export async function downloadPicture(p: Picture) {
  try { const r = await fetch(p.url); if (!r.ok) throw new Error(); const b = await r.blob(); save(b, `${p.name}.${b.type.includes('svg') ? 'svg' : b.type.includes('png') ? 'png' : b.type.includes('webp') ? 'webp' : 'jpg'}`) }
  catch { ElMessage.error('下载失败，请重试') }
}
// Standard uncompressed ZIP, UTF-8 names, for local prototype files only.
function crc32(bytes: Uint8Array) { let crc = -1; for (const b of bytes) { crc ^= b; for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0) } return (crc ^ -1) >>> 0 }
export async function downloadSet(images: Picture[], name: string) {
  try {
    const parts: Uint8Array[] = [], directory: Uint8Array[] = []; let offset = 0
    for (let i = 0; i < images.length; i++) {
      const response = await fetch(images[i].url); if (!response.ok) throw new Error()
      const blob = await response.blob(); const data = new Uint8Array(await blob.arrayBuffer())
      const ext = blob.type.includes('svg') ? 'svg' : blob.type.includes('png') ? 'png' : blob.type.includes('webp') ? 'webp' : 'jpg'
      const filename = new TextEncoder().encode(`${String(i + 1).padStart(2, '0')}.${ext}`), crc = crc32(data)
      const h = new Uint8Array(30 + filename.length), v = new DataView(h.buffer)
      v.setUint32(0, 0x04034b50, true); v.setUint16(4, 20, true); v.setUint16(6, 0x800, true)
      v.setUint32(14, crc, true); v.setUint32(18, data.length, true); v.setUint32(22, data.length, true); v.setUint16(26, filename.length, true); h.set(filename, 30)
      const c = new Uint8Array(46 + filename.length), d = new DataView(c.buffer)
      d.setUint32(0, 0x02014b50, true); d.setUint16(4, 20, true); d.setUint16(6, 20, true); d.setUint16(8, 0x800, true)
      d.setUint32(16, crc, true); d.setUint32(20, data.length, true); d.setUint32(24, data.length, true); d.setUint16(28, filename.length, true); d.setUint32(42, offset, true); c.set(filename, 46)
      parts.push(h, data); directory.push(c); offset += h.length + data.length
    }
    const end = new Uint8Array(22), e = new DataView(end.buffer)
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, images.length, true); e.setUint16(10, images.length, true); e.setUint32(12, directory.reduce((n, p) => n + p.length, 0), true); e.setUint32(16, offset, true)
    save(new Blob([...parts, ...directory, end], { type: 'application/zip' }), `${name}-演示图片.zip`)
  } catch { ElMessage.error('打包失败，请重试') }
}
