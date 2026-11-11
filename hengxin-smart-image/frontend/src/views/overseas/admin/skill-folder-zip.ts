import { isDirectory, type SkillPackage, type SkillTransferApi } from '../../../api/overseas/skill-transfers'
import { folderLimits, safeSegment, sha256 } from './skill-folder-read'

/** ZIP 只包含服务端固定 release 清单的原始字节；下载不会删除远端包。 */
export async function buildSkillZip(id: string, descriptor: SkillPackage, api: Pick<SkillTransferApi, 'file'>, progress: (done: number, total: number) => void = () => {}): Promise<Blob> {
  const entries = Object.entries(descriptor.entries)
  const validSegment = (name: string) => safeSegment(name) && !name.includes(':')
  if (!validSegment(descriptor.rootName)) throw Error('服务端返回了无效的根目录名')
  if (entries.length > folderLimits.entries) throw Error('目录条目超过 2000 项')
  const names = new Set<string>()
  let totalBytes = 0, files = 0
  for (const [path, entry] of entries) {
    if (!path.replace(/\/$/, '').split('/').every(validSegment) || path.endsWith('/') !== isDirectory(entry)) throw Error('服务端返回了无效路径')
    const name = path.replace(/\/$/, '').normalize('NFC').toLowerCase()
    if (names.has(name)) throw Error('服务端返回了冲突路径')
    names.add(name)
    if (!isDirectory(entry)) {
      if (!Number.isSafeInteger(entry.size) || entry.size < 0 || entry.size > folderLimits.file) throw Error('单文件大小无效或超过 64 MiB')
      totalBytes += entry.size; files++
    }
  }
  if (totalBytes > folderLimits.bytes || files > folderLimits.files) throw Error('文件夹超过 256 MiB 或 1000 个文件')
  const { Zip, ZipPassThrough } = await import('fflate')
  const chunks: BlobPart[] = []
  let failure: Error | undefined, complete = false
  const zip = new Zip((error, bytes, final) => {
    if (error) { failure = error; return }
    chunks.push(bytes); complete = final
  })
  const add = (path: string, bytes: Uint8Array) => {
    const file = new ZipPassThrough(path)
    if (path.endsWith('/')) file.attrs = 0x10
    zip.add(file); file.push(bytes, true)
    if (failure) throw failure
  }
  try {
    add(descriptor.rootName + '/', new Uint8Array())
    let done = 0
    for (const [path, entry] of entries) {
      let bytes = new ArrayBuffer(0)
      if (!isDirectory(entry)) {
        bytes = await api.file(id, descriptor.release, path)
        if (bytes.byteLength !== entry.size || await sha256(bytes) !== entry.sha256) throw Error(`下载内容校验失败：${path}`)
      }
      add(descriptor.rootName + '/' + path, new Uint8Array(bytes))
      progress(++done, entries.length)
    }
    zip.end()
    if (failure) throw failure
    if (!complete) throw Error('ZIP 文件生成未完成，请重试')
    return new Blob(chunks, { type: 'application/zip' })
  } catch (reason) { zip.terminate(); throw reason }
}

export async function downloadSkillZip(id: string, descriptor: SkillPackage, api: Pick<SkillTransferApi, 'file'>, progress: (done: number, total: number) => void) {
  const blob = await buildSkillZip(id, descriptor, api, progress)
  const url = URL.createObjectURL(blob), anchor = document.createElement('a')
  anchor.href = url; anchor.download = descriptor.rootName + '.zip'
  document.body.appendChild(anchor)
  try { anchor.click() } finally { anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 60_000) }
}
