import test from 'node:test'
import assert from 'node:assert/strict'
import { webcrypto } from 'node:crypto'
import { unzipSync } from 'fflate'
import { buildSkillZip } from '../src/views/shared/skills/skill-folder-zip'
import { scanFolder } from '../src/views/shared/skills/skill-folder-read'
import * as Save from '../src/views/shared/skills/skill-folder-save'
import * as Transfers from '../src/api/overseas/skill-transfers'
import { IdentityError } from '../src/api/identity/request'
import { formatAttachmentSize } from '../src/api/overseas/attachment-download'
import { dirNode, fileNode } from './skill-folders-fixture'
import { all, compile, flush, mount, text, type Node } from './membership-test-harness'

async function fixture() {
  const folder = await scanFolder(dirNode('完整技能', [fileNode('SKILL.md'), dirNode('空目录', []), dirNode('素材', [fileNode('原图.bin', new Uint8Array([0, 255, 128, 13, 10, 0])), fileNode('empty.txt', '')])]))
  const descriptor = { ...folder, release: 'frozen-release', checksum: 'fixed-checksum' }
  const reads: string[] = []
  const api = { file: async (id: string, release: string, path: string) => { assert.equal(id, 'skill'); assert.equal(release, descriptor.release); reads.push(path); return folder.files.get(path)!.arrayBuffer() } }
  return { folder, descriptor, api, reads }
}

test('HTTP ZIP 解压保持完整根目录、空目录、Unicode名称和全部原始字节', async t => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto')!
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) } })
  t.after(() => Object.defineProperty(globalThis, 'crypto', original))
  const f = await fixture(), progress: number[] = []
  const blob = await buildSkillZip('skill', f.descriptor, f.api, done => progress.push(done))
  assert.equal(blob.type, 'application/zip')
  const files = unzipSync(new Uint8Array(await blob.arrayBuffer()))
  assert.deepEqual(Object.keys(files).sort(), [f.folder.rootName + '/', ...Object.keys(f.folder.entries).map(path => f.folder.rootName + '/' + path)].sort())
  assert.equal(files['完整技能/空目录/'].length, 0)
  for (const [path, file] of f.folder.files) assert.deepEqual(files['完整技能/' + path], new Uint8Array(await file.arrayBuffer()))
  assert.equal(progress.at(-1), Object.keys(f.folder.entries).length)
  assert.equal(f.reads.length, f.folder.files.size)
})

test('ZIP 拒绝损坏内容、网络中断、危险路径和过量数据，不产生成功文件', async () => {
  const f = await fixture()
  await assert.rejects(buildSkillZip('skill', f.descriptor, { file: async () => new ArrayBuffer(0) }), /下载内容校验失败/)
  await assert.rejects(buildSkillZip('skill', f.descriptor, { file: async () => { throw Error('连接中断') } }), /连接中断/)
  for (const rootName of ['../bad', 'C:', 'bad\\root']) await assert.rejects(buildSkillZip('skill', { ...f.descriptor, rootName }, f.api), /无效/)
  for (const path of ['../escape', '/absolute', 'nested/../escape', 'C:/escape']) {
    await assert.rejects(buildSkillZip('skill', { ...f.descriptor, entries: { [path]: { size: 0, sha256: '0'.repeat(64) } } }, f.api), /无效路径/)
  }
  await assert.rejects(buildSkillZip('skill', { ...f.descriptor, entries: { 'large': { size: 64 * 1024 * 1024 + 1, sha256: '0'.repeat(64) } } }, f.api), /64 MiB/)
  await assert.rejects(buildSkillZip('skill', { ...f.descriptor, entries: { 'same/': { directory: true }, 'same': { size: 0, sha256: '0'.repeat(64) } } }, f.api), /冲突路径/)
})

test('HTTP 真实保存组件使用 ZIP，成功仅告知已发起下载，失败不误报和不删除远端', async () => {
  const f = await fixture(); let fail = true, downloads = 0, packages = 0
  const component = compile('views/shared/skills/SkillFolderActions.vue', {
    '@/api/shared/skill-transfers': Transfers, '@/api/identity/request': { IdentityError }, '@/utils/attachment-size': { formatAttachmentSize },
    './skill-folder-save': { ...Save, supportsDirectorySave: () => false, chooseParent: () => { throw Error('不应打开目录选择器') } },
    './skill-folder-zip': { downloadSkillZip: async (...args: Parameters<typeof buildSkillZip>) => { if (fail) throw Error('连接中断'); await buildSkillZip(...args); downloads++ } },
    'element-plus': { ElMessageBox: { confirm: () => { throw Error('不应删除远端') } } }
  })
  const api = { ...f.api, package: async () => { packages++; return f.descriptor }, remove: () => { throw Error('不应删除远端') } }
  const view = mount(component, { skill: { id: 'skill' }, api, canManage: false })
  async function clickSave(root: Node) { const button = all(root).find(n => n.tag === 'ElButton' && text(n) === '下载 ZIP')!; assert.ok(button); await (button.props.onClick as () => Promise<void>)(); await flush() }
  try {
    await clickSave(view.root); assert.match(text(view.root), /连接中断/); assert.doesNotMatch(text(view.root), /已发起|保存完成/)
    fail = false; await clickSave(view.root)
    assert.equal(downloads, 1); assert.equal(packages, 2)
    assert.match(text(view.root), /已发起完整文件夹 ZIP 下载/); assert.doesNotMatch(text(view.root), /全部目录和文件已读回核验/)
  } finally { view.close() }
})

test('国内模式即使浏览器支持目录选择也只提供 ZIP 下载', async () => {
  const f = await fixture(); let downloads = 0
  const component = compile('views/shared/skills/SkillFolderActions.vue', {
    '@/api/shared/skill-transfers': Transfers, '@/api/identity/request': { IdentityError }, '@/utils/attachment-size': { formatAttachmentSize },
    './skill-folder-save': { ...Save, supportsDirectorySave: () => true, chooseParent: () => { throw Error('国内不应打开目录选择器') } },
    './skill-folder-zip': { downloadSkillZip: async (...args: Parameters<typeof buildSkillZip>) => { await buildSkillZip(...args); downloads++ } },
    'element-plus': { ElMessageBox: { confirm: () => { throw Error('不应删除') } } }
  })
  const api = { ...f.api, package: async () => f.descriptor }
  const view = mount(component, { skill: { id: 'skill' }, api, canManage: false, zipOnly: true })
  try {
    const button = all(view.root).find(n => n.tag === 'ElButton' && text(n) === '下载 ZIP')!
    assert.ok(button); await (button.props.onClick as () => Promise<void>)(); await flush()
    assert.equal(downloads, 1); assert.doesNotMatch(text(view.root), /保存为文件夹/)
  } finally { view.close() }
})
