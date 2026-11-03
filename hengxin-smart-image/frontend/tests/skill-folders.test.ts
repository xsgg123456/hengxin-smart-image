import test from 'node:test'
import assert from 'node:assert/strict'
import { createSkillTransferApi, isTransfer, type SkillPackage } from '../src/api/overseas/skill-transfers'
import { IdentityError } from '../src/api/identity/request'
import { droppedRoot, scanFolder, folderTree } from '../src/views/overseas/admin/skill-folder-read'
import { prepareFolderSave, verifyFolder, writeFolder } from '../src/views/overseas/admin/skill-folder-save'
import { dirNode, fileNode, MemoryDirectory, skillSource } from './skill-folders-fixture'
async function fixture() {
  const binary = new Uint8Array([0, 255, 128, 13, 10, 0])
  const folder = await scanFolder(dirNode('原始目录', [fileNode('SKILL.md'), dirNode('empty', []), dirNode('assets', [fileNode('原图.bin', binary)])]))
  const descriptor: SkillPackage = { ...folder, name: folder.name, displayName: folder.displayName, description: folder.description, release: 'fixed-r1', checksum: 'fixed-checksum' }
  const requests: string[] = []
  const api = { file: async (_id: string, release: string, path: string) => { requests.push(release); return folder.files.get(path)!.arrayBuffer() } }
  return { folder, descriptor, api, requests }
}
test('完整分页枚举超过100项，同步保留空目录、二进制、名称描述和树', async () => {
  const count = { reads: 0 }, children = [fileNode('SKILL.md'), ...Array.from({ length: 205 }, (_, i) => fileNode(`file${i}.bin`, new Uint8Array([i % 256]))), dirNode('empty', [])]
  const folder = await scanFolder(dirNode('root', children, count))
  assert.equal(count.reads, 4); assert.equal(folder.files.size, 206); assert.equal(Object.keys(folder.entries).length, 207)
  assert.deepEqual(folder.entries['empty/'], { directory: true }); assert.equal(folder.displayName, '测试技能'); assert.equal(folder.description, '完整目录测试')
  assert.equal(folderTree(folder)[0].children!.length, 207)
  assert.deepEqual(new Uint8Array(await folder.files.get('file128.bin')!.arrayBuffer()), new Uint8Array([128]))
})
test('读取失败、目录能力缺失、重复路径、越界、缺根SKILL和超数量整体拒绝', async () => {
  const broken = fileNode('broken'); broken.file = (_resolve, reject) => reject(new DOMException('拒绝读取'))
  await assert.rejects(scanFolder(dirNode('root', [fileNode('SKILL.md'), broken])), /拒绝读取/)
  await assert.rejects(scanFolder({ name: 'root', isDirectory: true, isFile: false }), /完整读取/)
  await assert.rejects(scanFolder(dirNode('root', [fileNode('SKILL.md'), fileNode('A'), fileNode('a')])), /冲突/)
  await assert.rejects(scanFolder(dirNode('root', [fileNode('../escape')])), /不支持/)
  await assert.rejects(scanFolder(dirNode('root', [dirNode('empty', [])])), /SKILL.md/)
  await assert.rejects(scanFolder(dirNode('root', [fileNode('SKILL.md'), ...Array.from({ length: 1000 }, (_, i) => fileNode('f' + i))])), /1000/)
  await assert.rejects(scanFolder(dirNode('root', [fileNode('SKILL.md'), ...Array.from({ length: 2000 }, (_, i) => dirNode('d' + i, []))])), /2000/)
})
test('拖入文件和多根目录直接拒绝，不退化为漏空目录的FileList', () => {
  for (const items of [[], [{ kind: 'file', webkitGetAsEntry: () => fileNode('SKILL.md') }], [{ kind: 'file' }], [{ kind: 'file' }, { kind: 'file' }]]) assert.throws(() => droppedRoot({ items } as unknown as DataTransfer), /完整文件夹|完整文件夹|目录/)
})
test('单文件64MiB上限先校验，超限不会读取内容或产生可上传清单', async () => {
  const oversize = fileNode('oversize.bin'); let read = false
  oversize.file = resolve => {
    const file = new File([], 'oversize.bin')
    Object.defineProperty(file, 'size', { value: 64 * 1024 * 1024 + 1 })
    file.arrayBuffer = async () => { read = true; return new ArrayBuffer(0) }
    resolve(file)
  }
  await assert.rejects(scanFolder(dirNode('root', [fileNode('SKILL.md'), oversize])), /64 MiB/)
  assert.equal(read, false)
})
test('保存固定发布版本、完整空目录及原始字节，逐文件与全清单读回', async () => {
  const f = await fixture(), parent = new MemoryDirectory('Downloads'), save = await prepareFolderSave(parent, 'id', f.descriptor), progress: number[] = []
  await writeFolder(save, f.api, done => progress.push(done)); await verifyFolder(save)
  assert.equal(progress.at(-1), Object.keys(f.folder.entries).length); assert.ok(f.requests.every(r => r === 'fixed-r1'))
  const root = await parent.getDirectoryHandle('原始目录'); assert.equal((await root.getDirectoryHandle('empty')).children.size, 0)
  const asset = await (await root.getDirectoryHandle('assets')).getFileHandle('原图.bin')
  assert.deepEqual(new Uint8Array(await (await asset.getFile()).arrayBuffer()), new Uint8Array([0, 255, 128, 13, 10, 0]))
  assert.deepEqual([...root.children.keys()].sort(), ['SKILL.md', 'assets', 'empty'])
  await assert.rejects(prepareFolderSave(parent, 'id', f.descriptor), /同名/)
})
test('中断、下载损坏和磁盘损坏不报成功，保留原句柄固定版本核验重试', async () => {
  const f = await fixture(), parent = new MemoryDirectory('Downloads'), save = await prepareFolderSave(parent, 'id', f.descriptor)
  let calls = 0
  await assert.rejects(writeFolder(save, { file: async (...args) => { if (++calls === 2) throw Error('连接中断'); return f.api.file(...args) } }, () => {}), /连接中断/)
  await assert.rejects(verifyFolder(save), /不完整/)
  await writeFolder(save, f.api, () => {}); await verifyFolder(save)
  await assert.rejects(writeFolder(save, { file: async () => new Uint8Array([0]).buffer }, () => {}), /下载内容校验失败/)
  const diskFile = await (save.root as MemoryDirectory).getFileHandle('SKILL.md'); diskFile.corrupt = true
  await assert.rejects(writeFolder(save, f.api, () => {}), /读回校验失败/)
  diskFile.corrupt = false
  await assert.rejects(writeFolder(save, f.api, () => {}), /冲突/)
  diskFile.bytes = await f.folder.files.get('SKILL.md')!.arrayBuffer(); diskFile.fail = true
  await assert.rejects(writeFolder(save, f.api, () => {}), /磁盘写入失败/)
  diskFile.fail = false; await writeFolder(save, f.api, () => {})
  await (save.root as MemoryDirectory).getDirectoryHandle('extra', { create: true })
  await assert.rejects(verifyFolder(save), /额外条目/)
})
test('检查后目标被并发创建并写入，拒绝复用该目录', async () => {
  const f = await fixture(), parent = new MemoryDirectory('Downloads'), original = parent.getDirectoryHandle.bind(parent)
  parent.getDirectoryHandle = async (name, options) => { const root = await original(name, options); await root.getFileHandle('用户文件', { create: true }); return root }
  await assert.rejects(prepareFolderSave(parent, 'id', f.descriptor), /其他操作写入/)
})
test('传输API保留二进制、幂等键、原目录和固定release；拒绝格式错误并保留冲突', async () => {
  const folder = await scanFolder(dirNode('root', [fileNode('SKILL.md', skillSource)])), state = { ...folder, id: 't', status: 'uploading', received: [] }
  const fetcher: typeof fetch = async (url, options) => {
    assert.equal(options?.credentials, 'include')
    if (String(url).endsWith('/skill-transfers')) { assert.equal((options!.headers as Record<string, string>)['Idempotency-Key'], 'same-key'); assert.equal(JSON.parse(String(options?.body)).rootName, 'root') }
    if (options?.method === 'PUT') { assert.ok(options.body instanceof Blob); assert.equal(await options.body.text(), skillSource); assert.match(String(url), /path=SKILL.md/) }
    return new Response(JSON.stringify(state))
  }
  const api = createSkillTransferApi(fetcher); await api.create(folder, 'same-key'); await api.upload('t', 'SKILL.md', folder.files.get('SKILL.md')!)
  assert.equal(isTransfer({ ...state, received: [4] }), false)
  assert.equal(isTransfer({ ...state, error: null }), true)
  assert.equal(isTransfer({ ...state, change: 'unknown' }), false)
  await assert.rejects(createSkillTransferApi(async () => new Response('{}', { status: 409 })).remove('id', 'release', 'checksum', 4), (e: unknown) => e instanceof IdentityError && e.status === 409)
})

test('YAML预览支持引号键、注释、转义和折叠标量，原始文件不变', async () => {
  const examples = [
    { yaml: '"name": "quoted" # comment\n\'description\': "line\\n\\u4E2D" # ignored', name: 'quoted', description: 'line\n中' },
    { yaml: 'name: folded\ndescription: >- # folded\n  first line\n  second line', name: 'folded', description: 'first line second line' },
    { yaml: 'name: literal\ndescription: |+\n  first\n  second\n', name: 'literal', description: 'first\nsecond' },
    { yaml: 'defaults: &defaults { name: merged, description: inherited }\n<<: *defaults', name: 'merged', description: 'inherited' },
    { yaml: 'name: old\nname: final\ndescription: "yes"', name: 'final', description: 'yes' }
  ]
  for (const example of examples) {
    const source = '\uFEFF--- \r\n' + example.yaml.replaceAll('\n', '\r\n') + '\r\n--- \r\nbody'
    const result = await scanFolder(dirNode('root', [fileNode('SKILL.md', source)]))
    assert.equal(result.name, example.name); assert.equal(result.description, example.description)
    assert.equal(result.displayName, example.name)
    assert.deepEqual(new Uint8Array(await result.files.get('SKILL.md')!.arrayBuffer()), new TextEncoder().encode(source))
  }
})
test('标题按CommonMark解析，跳过代码/HTML中的伪标题并提取格式化文本', async () => {
  const cases = [
    ['```md\n# fake\n```\n# **真实** `code` [link](https://example.org) ![图](a.png) ###', '真实 code link 图'],
    ['    # fake\n\n真实标题\n========', '真实标题'],
    ['<div>\n# fake\n</div>\n\n# 真标题', '真标题'],
    ['~~~\n# fake\n~~~', 'fixture']
  ]
  for (const [body, expected] of cases) {
    const result = await scanFolder(dirNode('root', [fileNode('SKILL.md', '---\nname: fixture\ndescription: test\n---\n' + body)]))
    assert.equal(result.displayName, expected)
  }
})
test('本地YAML能力与别名预算不足交由服务器裁定，超长frontmatter在解析前拒绝', async () => {
  const aliases = 'a: &a [x,x,x,x,x,x,x,x,x,x]\nb: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a,*a]\nc: [*b,*b,*b,*b,*b,*b,*b,*b,*b,*b]'
  for (const yaml of ['name: !server-tag demo\ndescription: test', 'name: demo\ndescription: test\n' + aliases, 'name: [malformed']) {
    const result = await scanFolder(dirNode('root', [fileNode('SKILL.md', '---\n' + yaml + '\n---\n# 标题')]))
    assert.equal(result.displayName, '标题'); assert.equal(result.description, '元数据待服务器校验后显示')
  }
  await assert.rejects(scanFolder(dirNode('root', [fileNode('SKILL.md', '---\nname: demo\ndescription: ' + 'x'.repeat(65536) + '\n---\n')])), /长度合规/)
})
