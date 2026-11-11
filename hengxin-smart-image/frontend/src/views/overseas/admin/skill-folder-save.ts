import { isDirectory, type SkillPackage, type SkillTransferApi } from '../../../api/overseas/skill-transfers'
import { safeSegment, sha256 } from './skill-folder-read'
export interface LocalFile {
  kind: 'file'; name: string; getFile(): Promise<File>
  isSameEntry?(other: LocalFile | LocalDirectory): Promise<boolean>
  createWritable(): Promise<{ write(bytes: ArrayBuffer): Promise<void>; close(): Promise<void>; abort(): Promise<void> }>
}
export interface LocalDirectory {
  kind: 'directory'; name: string
  isSameEntry?(other: LocalFile | LocalDirectory): Promise<boolean>
  getDirectoryHandle(name: string, options?: { create?: boolean }): Promise<LocalDirectory>
  getFileHandle(name: string, options?: { create?: boolean }): Promise<LocalFile>
  values(): AsyncIterableIterator<LocalDirectory | LocalFile>
}
export interface FolderSave { id: string; descriptor: SkillPackage; root: LocalDirectory }
type LocalEntry = LocalFile | LocalDirectory
interface OwnedEntry { handle: LocalEntry; fingerprint?: string }
interface SaveOwnership { parent: LocalDirectory; entries: Map<string, OwnedEntry>; writing: boolean }
const ownership = new WeakMap<FolderSave, SaveOwnership>()
const key = (name: string) => name.normalize('NFC').toLowerCase()
function conflict(path: string): never { throw new Error(`本地保存冲突：${path} 已被其他操作创建、替换或修改，不会覆盖；请另选父目录`) }
async function sameEntry(left: LocalEntry, right: LocalEntry): Promise<boolean> {
  return left.kind === right.kind && (left.isSameEntry ? left.isSameEntry(right) : left === right)
}
async function fingerprint(file: LocalFile): Promise<string> {
  const data = await file.getFile()
  return `${data.size}:${await sha256(await data.arrayBuffer())}`
}
async function existing(parent: LocalDirectory, name: string): Promise<LocalEntry | undefined> {
  for await (const child of parent.values()) if (key(child.name) === key(name)) {
    if (child.name !== name) conflict(name)
    return child
  }
}
function state(save: FolderSave): SaveOwnership {
  const result = ownership.get(save)
  if (!result) throw new Error('本地保存会话已失效，请重新选择父目录')
  return result
}
async function assertOwned(save: FolderSave, path: string, handle: LocalEntry): Promise<void> {
  const owned = state(save).entries.get(path)
  if (!owned || !await sameEntry(owned.handle, handle)) conflict(path)
  if (handle.kind === 'file' && await fingerprint(handle) !== owned.fingerprint) conflict(path)
}
async function checkOwnership(save: FolderSave): Promise<void> {
  const current = state(save)
  await assertRoot(save)
  const present = new Set<string>()
  async function walk(dir: LocalDirectory, prefix: string) {
    for await (const child of dir.values()) {
      const path = prefix + child.name + (child.kind === 'directory' ? '/' : '')
      await assertOwned(save, path, child)
      present.add(path)
      if (child.kind === 'directory') await walk(child, path)
    }
  }
  await walk(save.root, '')
  // Missing entries can be recreated, but a replacement appearing later is unowned.
  for (const path of current.entries.keys()) if (!present.has(path)) current.entries.delete(path)
}
async function assertRoot(save: FolderSave): Promise<void> {
  const root = await existing(state(save).parent, save.descriptor.rootName)
  if (!root || !await sameEntry(save.root, root)) conflict(save.descriptor.rootName)
}
type PickerWindow = Window & { showDirectoryPicker?: (options: { mode: 'readwrite' }) => Promise<LocalDirectory> }
export function supportsDirectorySave(): boolean { return typeof window !== 'undefined' && typeof (window as PickerWindow).showDirectoryPicker === 'function' }
export function chooseParent(): Promise<LocalDirectory> {
  const picker = (window as PickerWindow).showDirectoryPicker
  if (!picker) return Promise.reject(new Error('此浏览器不支持保存完整文件夹，请使用新版 Chrome 或 Edge'))
  return picker.call(window, { mode: 'readwrite' })
}
export async function prepareFolderSave(parent: LocalDirectory, id: string, descriptor: SkillPackage): Promise<FolderSave> {
  if (!safeSegment(descriptor.rootName)) throw new Error('服务端返回了无效的根目录名')
  for (const path of Object.keys(descriptor.entries)) if (!path.replace(/\/$/, '').split('/').every(safeSegment)) throw new Error('服务端返回了无效路径')
  for await (const entry of parent.values()) if (entry.name.normalize('NFC').toLowerCase() === descriptor.rootName.normalize('NFC').toLowerCase()) throw new Error(`目标已存在同名文件夹或文件「${descriptor.rootName}」，请选择其他父目录，不会覆盖`)
  const root = await parent.getDirectoryHandle(descriptor.rootName, { create: true })
  // Check again after creation, so a concurrently populated destination is never overwritten.
  for await (const _entry of root.values()) throw new Error('目标目录已被其他操作写入，请选择其他父目录，不会覆盖')
  const save = { id, descriptor, root }
  ownership.set(save, { parent, entries: new Map(), writing: false })
  return save
}
async function directory(save: FolderSave, path: string): Promise<LocalDirectory> {
  await assertRoot(save)
  let current = save.root, prefix = ''
  for (const segment of path.split('/').filter(Boolean)) {
    prefix += segment + '/'
    const child = await existing(current, segment)
    if (child) {
      await assertOwned(save, prefix, child)
      if (child.kind !== 'directory') conflict(prefix)
      current = child
    } else {
      current = await current.getDirectoryHandle(segment, { create: true })
      for await (const _entry of current.values()) conflict(prefix)
      for (const ownedPath of state(save).entries.keys()) if (ownedPath.startsWith(prefix)) state(save).entries.delete(ownedPath)
      state(save).entries.set(prefix, { handle: current })
    }
  }
  return current
}
async function targetFile(save: FolderSave, parent: LocalDirectory, path: string, name: string): Promise<LocalFile> {
  const child = await existing(parent, name)
  if (child) {
    await assertOwned(save, path, child)
    if (child.kind !== 'file') conflict(path)
    return child
  }
  // File System Access has no atomic exclusive-create. Recheck the newly returned
  // handle before claiming it; never truncate a file populated during creation.
  const target = await parent.getFileHandle(name, { create: true })
  const empty = await target.getFile()
  if (empty.size !== 0) conflict(path)
  state(save).entries.set(path, { handle: target, fingerprint: `0:${await sha256(await empty.arrayBuffer())}` })
  return target
}
export async function verifyFolder(save: FolderSave): Promise<void> {
  const actual = new Map<string, string>(), expected = save.descriptor.entries
  async function walk(dir: LocalDirectory, parent: string) {
    for await (const child of dir.values()) {
      const path = parent + child.name + (child.kind === 'directory' ? '/' : '')
      if (!(path in expected)) throw new Error(`本地目录含额外条目：${path}`)
      if (child.kind === 'directory') { if (!isDirectory(expected[path])) throw new Error(`目录类型不符：${path}`); actual.set(path, 'directory'); await walk(child, path) }
      else {
        const entry = expected[path], file = await child.getFile()
        if (isDirectory(entry) || file.size !== entry.size || await sha256(await file.arrayBuffer()) !== entry.sha256) throw new Error(`读回校验失败：${path}`)
        actual.set(path, 'file')
      }
    }
  }
  await walk(save.root, '')
  if (actual.size !== Object.keys(expected).length) throw new Error('本地文件夹不完整，文件或空目录缺失')
}
export async function writeFolder(save: FolderSave, api: Pick<SkillTransferApi, 'file'>, progress: (done: number, total: number) => void): Promise<void> {
  const current = state(save)
  if (current.writing) throw new Error('此文件夹正在保存，请等待当前操作结束后重试')
  current.writing = true
  try { await writeOwnedFolder(save, api, progress) } finally { current.writing = false }
}
async function writeOwnedFolder(save: FolderSave, api: Pick<SkillTransferApi, 'file'>, progress: (done: number, total: number) => void): Promise<void> {
  await checkOwnership(save)
  const entries = Object.entries(save.descriptor.entries), total = entries.length
  let done = 0
  for (const [path, entry] of entries) {
    if (isDirectory(entry)) await directory(save, path)
    else {
      const bytes = await api.file(save.id, save.descriptor.release, path)
      if (bytes.byteLength !== entry.size || await sha256(bytes) !== entry.sha256) throw new Error(`下载内容校验失败：${path}`)
      const parts = path.split('/'), name = parts.pop()!, parent = await directory(save, parts.join('/'))
      const target = await targetFile(save, parent, path, name), writer = await target.createWritable()
      try {
        const linked = await existing(parent, name)
        if (!linked || !await sameEntry(target, linked)) conflict(path)
        await assertOwned(save, path, linked)
        await writer.write(bytes); await writer.close()
      } catch (reason) { await writer.abort().catch(() => {}); throw reason }
      const readback = await target.getFile()
      if (readback.size !== entry.size || await sha256(await readback.arrayBuffer()) !== entry.sha256) throw new Error(`写入后读回校验失败：${path}`)
      state(save).entries.set(path, { handle: target, fingerprint: `${entry.size}:${entry.sha256}` })
    }
    progress(++done, total)
  }
  await checkOwnership(save)
  await verifyFolder(save)
}
