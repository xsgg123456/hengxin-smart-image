import { type FolderNode } from '../src/views/shared/skills/skill-folder-read'
import { type LocalDirectory, type LocalFile } from '../src/views/shared/skills/skill-folder-save'
export const skillSource = '---\nname: fixture\ndescription: 完整目录测试\n---\n# 测试技能\n'
export function fileNode(name: string, bytes: BlobPart = skillSource): FolderNode {
  return { name, isDirectory: false, isFile: true, file: resolve => resolve(new File([bytes], name)) }
}
export function dirNode(name: string, children: FolderNode[], count?: { reads: number }): FolderNode {
  return { name, isDirectory: true, isFile: false, createReader() {
    let offset = 0
    return { readEntries(resolve) { if (count) count.reads++; const batch = children.slice(offset, offset + 100); offset += batch.length; resolve(batch) } }
  } }
}
export class MemoryDirectory implements LocalDirectory {
  kind = 'directory' as const
  children = new Map<string, MemoryDirectory | MemoryFile>()
  constructor(public name: string) {}
  async getDirectoryHandle(name: string, options?: { create?: boolean }) {
    let child = this.children.get(name)
    if (!child && options?.create) { child = new MemoryDirectory(name); this.children.set(name, child) }
    if (!(child instanceof MemoryDirectory)) throw new DOMException('missing directory', 'NotFoundError')
    return child
  }
  async getFileHandle(name: string, options?: { create?: boolean }) {
    let child = this.children.get(name)
    if (!child && options?.create) { child = new MemoryFile(name); this.children.set(name, child) }
    if (!(child instanceof MemoryFile)) throw new DOMException('missing file', 'NotFoundError')
    return child
  }
  async *values() { yield* this.children.values() }
}
export class MemoryFile implements LocalFile {
  kind = 'file' as const; bytes = new ArrayBuffer(0); corrupt = false; fail = false
  constructor(public name: string) {}
  async getFile() { return new File([this.bytes], this.name) }
  async createWritable() {
    return { write: async (bytes: ArrayBuffer) => { if (this.fail) throw Error('磁盘写入失败'); this.bytes = this.corrupt ? new Uint8Array([1, 2, 3]).buffer : bytes.slice(0) }, close: async () => {}, abort: async () => {} }
  }
}
