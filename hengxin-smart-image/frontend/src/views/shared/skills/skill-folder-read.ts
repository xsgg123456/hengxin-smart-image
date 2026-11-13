import { sha256 } from '../../../utils/browser-crypto'
export { sha256 } from '../../../utils/browser-crypto'
import { isDirectory, type FolderManifest } from '../../../api/shared/skill-transfers'
import { previewSkillMetadata } from './skill-folder-metadata'
export interface FolderNode {
  name: string; isDirectory: boolean; isFile: boolean
  createReader?: () => { readEntries: (success: (entries: FolderNode[]) => void, fail: (reason: DOMException) => void) => void }
  file?: (success: (file: File) => void, fail: (reason: DOMException) => void) => void
}
export interface ScannedFolder extends FolderManifest { files: Map<string, File>; totalBytes: number; name: string; displayName: string; description: string }
export const folderLimits = { file: 64 * 1024 * 1024, bytes: 256 * 1024 * 1024, files: 1000, entries: 2000 }
export function safeSegment(name: string): boolean { return !!name && name !== '.' && name !== '..' && !/[\\/\u0000-\u001f]/.test(name) }
export function droppedRoot(data: DataTransfer): FolderNode {
  const items = Array.from(data.items)
  if (items.length !== 1 || items[0].kind !== 'file') throw new Error('请一次拖入一个完整文件夹')
  const root = items[0].webkitGetAsEntry?.()
  if (!root?.isDirectory) throw new Error('需要完整文件夹；当前浏览器无法读取目录时请使用新版 Chrome 或 Edge')
  return root as FolderNode
}
export async function scanFolder(root: FolderNode, progress: (count: number) => void = () => {}): Promise<ScannedFolder> {
  if (!root.isDirectory || !safeSegment(root.name)) throw new Error('无效的根文件夹')
  const result: ScannedFolder = { rootName: root.name, entries: Object.create(null), files: new Map(), totalBytes: 0, name: '', displayName: '', description: '' }
  const names = new Set<string>()
  async function visit(node: FolderNode, parent: string) {
    if (!safeSegment(node.name) || node.isDirectory === node.isFile) throw new Error(`不支持的目录条目：${parent}${node.name}`)
    const path = parent + node.name, normalized = path.normalize('NFC').toLowerCase()
    if (names.has(normalized)) throw new Error(`存在冲突路径：${path}`)
    names.add(normalized)
    if (names.size > folderLimits.entries) throw new Error('目录条目超过 2000 项')
    if (node.isDirectory) { result.entries[path + '/'] = { directory: true }; await children(node, path + '/') }
    else {
      if (!node.file) throw new Error(`无法读取文件：${path}`)
      const file = await new Promise<File>((resolve, reject) => node.file!(resolve, reject))
      if (file.size > folderLimits.file) throw new Error(`单文件超过 64 MiB：${path}`)
      result.totalBytes += file.size
      if (result.totalBytes > folderLimits.bytes || result.files.size >= folderLimits.files) throw new Error('文件夹超过 256 MiB 或 1000 个文件')
      result.entries[path] = { size: file.size, sha256: await sha256(await file.arrayBuffer()) }; result.files.set(path, file)
    }
    progress(names.size)
  }
  async function children(node: FolderNode, parent: string) {
    if (!node.createReader) throw new Error(`无法完整读取目录：${parent}`)
    const reader = node.createReader()
    while (true) {
      const batch = await new Promise<FolderNode[]>((resolve, reject) => reader.readEntries(resolve, reject))
      if (!batch.length) break
      for (const child of batch) await visit(child, parent)
    }
  }
  await children(root, '')
  const skill = result.files.get('SKILL.md')
  if (!skill) throw new Error('根文件夹必须包含 SKILL.md')
  const source = new TextDecoder('utf-8', { fatal: true }).decode(await skill.arrayBuffer())
  Object.assign(result, previewSkillMetadata(source, root.name))
  return result
}
export function folderTree(manifest: FolderManifest) {
  interface Tree { label: string; path: string; children?: Tree[] }
  const nodes = new Map<string, Tree>(), roots: Tree[] = []
  for (const [path, entry] of Object.entries(manifest.entries).sort(([a], [b]) => a.localeCompare(b))) {
    const parts = path.replace(/\/$/, '').split('/'), label = parts.pop()!, parent = parts.length ? parts.join('/') + '/' : ''
    const node: Tree = { path, label: isDirectory(entry) ? label + '/' : `${label} (${entry.size} B)`, ...(isDirectory(entry) ? { children: [] } : {}) }
    nodes.set(path, node); (nodes.get(parent)?.children || roots).push(node)
  }
  return [{ path: '', label: manifest.rootName + '/', children: roots }]
}
