import test from 'node:test'
import assert from 'node:assert/strict'
import type { SkillPackage } from '../src/api/overseas/skill-transfers'
import { scanFolder } from '../src/views/overseas/admin/skill-folder-read'
import { prepareFolderSave, verifyFolder, writeFolder, type LocalFile } from '../src/views/overseas/admin/skill-folder-save'
import { dirNode, fileNode, MemoryDirectory, MemoryFile } from './skill-folders-fixture'

async function fixture() {
  const folder = await scanFolder(dirNode('export', [fileNode('SKILL.md'), dirNode('assets', [fileNode('data.bin', 'binary')]), dirNode('empty', [])]))
  const descriptor: SkillPackage = { ...folder, release: 'r1', checksum: 'checksum' }
  const parent = new MemoryDirectory('Downloads'), save = await prepareFolderSave(parent, 'id', descriptor)
  const root = save.root as MemoryDirectory
  const api = { file: async (_id: string, _release: string, path: string) => folder.files.get(path)!.arrayBuffer() }
  return { folder, parent, save, root, api }
}
const noop = () => {}
const content = (value: string) => new TextEncoder().encode(value).buffer

test('prepare后出现同名用户文件、同bytes外来文件和空文件，均不覆盖', async () => {
  for (const source of ['USER-OWNED EXISTING BYTES', 'same', '']) {
    const f = await fixture(), target = await f.root.getFileHandle('SKILL.md', { create: true })
    target.bytes = source === 'same' ? await f.folder.files.get('SKILL.md')!.arrayBuffer() : content(source)
    const before = target.bytes.slice(0)
    await assert.rejects(writeFolder(f.save, f.api, noop), /冲突/)
    assert.deepEqual(target.bytes, before)
  }
})

test('重试前全树检查拒绝用户编辑与同内容替换句柄，保留所有文件字节', async () => {
  for (const replacement of [false, true]) {
    const f = await fixture()
    await writeFolder(f.save, f.api, noop)
    const original = await f.root.getFileHandle('SKILL.md')
    const target = replacement ? new MemoryFile('SKILL.md') : original
    target.bytes = replacement ? original.bytes.slice(0) : content('USER EDIT AFTER EXPORT')
    f.root.children.set('SKILL.md', target)
    const before = target.bytes.slice(0)
    let requests = 0
    await assert.rejects(writeFolder(f.save, { file: async (...args) => { requests++; return f.api.file(...args) } }, noop), /冲突/)
    assert.equal(requests, 0)
    assert.deepEqual(target.bytes, before)
  }
})

test('首次和重试时拒绝外来空目录、额外文件及替换目录', async () => {
  for (const kind of ['initial-directory', 'extra-file', 'extra-directory', 'replacement-directory']) {
    const f = await fixture()
    if (kind !== 'initial-directory') await writeFolder(f.save, f.api, noop)
    if (kind === 'extra-file') (await f.root.getFileHandle('user.txt', { create: true })).bytes = content('KEEP')
    else f.root.children.set(kind === 'extra-directory' ? 'extra' : 'empty', new MemoryDirectory(kind === 'extra-directory' ? 'extra' : 'empty'))
    let requests = 0
    await assert.rejects(writeFolder(f.save, { file: async (...args) => { requests++; return f.api.file(...args) } }, noop), /冲突/)
    assert.equal(requests, 0)
    if (kind === 'extra-file') assert.equal(await (await (await f.root.getFileHandle('user.txt')).getFile()).text(), 'KEEP')
  }
})

test('下载等待期间插入目标文件/目录或修改已导出文件，拒绝写入', async () => {
  for (const mode of ['file', 'directory', 'edit']) {
    const f = await fixture()
    if (mode === 'edit') await writeFolder(f.save, f.api, noop)
    let injected = false
    await assert.rejects(writeFolder(f.save, { file: async (...args) => {
      const bytes = await f.api.file(...args)
      if (!injected) {
        injected = true
        if (mode === 'directory') f.root.children.set('SKILL.md', new MemoryDirectory('SKILL.md'))
        else (await f.root.getFileHandle('SKILL.md', { create: true })).bytes = content('INSERTED DURING DOWNLOAD')
      }
      return bytes
    } }, noop), /冲突/)
    if (mode !== 'directory') assert.equal(await (await (await f.root.getFileHandle('SKILL.md')).getFile()).text(), 'INSERTED DURING DOWNLOAD')
  }
})

test('检查与create之间出现非空文件，不认领不覆盖', async () => {
  const f = await fixture(), original = f.root.getFileHandle.bind(f.root)
  f.root.getFileHandle = async (name, options) => {
    const handle = await original(name, options)
    if (options?.create) handle.bytes = content('RACING FILE')
    return handle
  }
  await assert.rejects(writeFolder(f.save, f.api, noop), /冲突/)
  assert.equal(await (await (await original('SKILL.md')).getFile()).text(), 'RACING FILE')
})

test('本次创建的零字节失败文件可重试；被用户填充后不得覆盖', async () => {
  for (const edited of [false, true]) {
    const f = await fixture(), original = f.root.getFileHandle.bind(f.root)
    f.root.getFileHandle = async (name, options) => { const file = await original(name, options); file.fail = true; return file }
    await assert.rejects(writeFolder(f.save, f.api, noop), /磁盘写入失败/)
    f.root.getFileHandle = original
    const target = await original('SKILL.md'); target.fail = false
    assert.equal(target.bytes.byteLength, 0)
    if (edited) {
      target.bytes = content('USER FILLED PLACEHOLDER')
      await assert.rejects(writeFolder(f.save, f.api, noop), /冲突/)
      assert.equal(await (await target.getFile()).text(), 'USER FILLED PLACEHOLDER')
    } else { await writeFolder(f.save, f.api, noop); await verifyFolder(f.save) }
  }
})

test('核验重试允许删除后的缺失文件和目录重新创建', async () => {
  const f = await fixture()
  await writeFolder(f.save, f.api, noop)
  f.root.children.delete('SKILL.md'); f.root.children.delete('assets'); f.root.children.delete('empty')
  await writeFolder(f.save, f.api, noop)
  await verifyFolder(f.save)
})

test('目标根目录被替换即冲突，原句柄及替换目录都不写入', async () => {
  const f = await fixture(), replacement = new MemoryDirectory('export')
  f.parent.children.set('export', replacement)
  await assert.rejects(writeFolder(f.save, f.api, noop), /冲突/)
  assert.equal(f.root.children.size, 0); assert.equal(replacement.children.size, 0)
})

test('createWritable等待期间被修改，abort而不覆盖新字节', async () => {
  const f = await fixture(), getFile = f.root.getFileHandle.bind(f.root)
  let aborted = false
  f.root.getFileHandle = async (name, options) => {
    const handle = await getFile(name, options), create = handle.createWritable.bind(handle)
    handle.createWritable = async () => {
      const writer = await create()
      handle.bytes = content('USER EDIT BEFORE WRITER READY')
      return { ...writer, abort: async () => { aborted = true; await writer.abort() } }
    }
    return handle
  }
  await assert.rejects(writeFolder(f.save, f.api, noop), /冲突/)
  assert.equal(aborted, true)
  assert.equal(await (await (await getFile('SKILL.md')).getFile()).text(), 'USER EDIT BEFORE WRITER READY')
})

test('不同JS句柄通过isSameEntry确认同一磁盘条目，可以完整保存和重试', async () => {
  const f = await fixture(), wrappers = new WeakMap<LocalFile, MemoryFile>()
  const values = f.root.values.bind(f.root)
  f.root.values = async function* () {
    for await (const original of values()) {
      if (original.kind === 'directory') { yield original; continue }
      const wrapper = Object.create(original) as MemoryFile & LocalFile
      wrapper.getFile = original.getFile.bind(original)
      wrapper.createWritable = original.createWritable.bind(original)
      wrappers.set(wrapper, original)
      wrapper.isSameEntry = async other => other === original || (other.kind === 'file' && wrappers.get(other) === original)
      Object.assign(original, { isSameEntry: wrapper.isSameEntry })
      yield wrapper
    }
  }
  await writeFolder(f.save, f.api, noop)
  await writeFolder(f.save, f.api, noop)
  await verifyFolder(f.save)
})
