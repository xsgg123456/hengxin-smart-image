import test from 'node:test'
import assert from 'node:assert/strict'
import * as Transfers from '../src/api/overseas/skill-transfers'
import * as Read from '../src/views/overseas/admin/skill-folder-read'
import * as Save from '../src/views/overseas/admin/skill-folder-save'
import { IdentityError } from '../src/api/identity/request'
import { all, click, compile, flush, mount, simple, text, type Node } from './membership-test-harness'
import { dirNode, fileNode, MemoryDirectory } from './skill-folders-fixture'
const uploadComponent = compile('views/overseas/admin/SkillFolderUpload.vue', { '@/api/overseas/skill-transfers': Transfers, './skill-folder-read': Read })
Object.assign(uploadComponent, { components: { ElTree: simple('ElTree'), ElProgress: simple('ElProgress') } })
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
let accept = true, chosen = 0, cancelled = false, confirmOptions: Record<string, unknown> | undefined
const parent = new MemoryDirectory('Downloads')
const actions = compile('views/overseas/admin/SkillFolderActions.vue', {
  '@/api/overseas/skill-transfers': Transfers, '@/api/identity/request': { IdentityError },
  './skill-folder-save': { ...Save, chooseParent: () => { chosen++; if (cancelled) return Promise.reject(new DOMException('cancel', 'AbortError')); return Promise.resolve(parent) } },
  'element-plus': { ElMessageBox: { confirm: async (_message: string, _title: string, options: Record<string, unknown>) => { confirmOptions = options; if (!accept) throw Error('cancel') } } }
})
const skill = { id: 'fixture', name: 'fixture', displayName: '测试技能', description: '说明', version: 7, enabled: false, platforms: [] }
const baseApi = () => Transfers.createSkillTransferApi(async () => { throw Error('不应请求真实API') })
async function drop(root: Node, node = dirNode('root', [fileNode('SKILL.md'), dirNode('empty', [])])) {
  const target = all(root).find(n => n.props.class === 'folder-drop')!
  await (target.props.onDrop as (e: unknown) => Promise<void>)({ preventDefault() {}, dataTransfer: { items: [{ kind: 'file', webkitGetAsEntry: () => node }] } }); await flush()
}
async function runClick(root: Node, label: string) {
  const button = all(root).find(n => n.tag === 'ElButton' && text(n) === label); assert.ok(button, label)
  await (button.props.onClick as () => Promise<void>)(); await flush()
}
function fixture(change: 'create' | 'update' | 'identical' = 'create') {
  let current: Transfers.SkillTransfer, puts = 0, installs = 0, creates = 0, fail = false
  const api: Transfers.SkillTransferApi = { ...baseApi(),
    create: async manifest => { creates++; current = { ...manifest, id: 't', status: 'uploading', received: [] }; return clone(current) },
    get: async () => clone(current),
    list: async () => ({ items: current ? [clone(current)] : [] }),
    upload: async (_id, path) => { puts++; if (fail) throw Error('连接中断'); current.received.push(path); return clone(current) },
    validate: async () => { current = { ...current, status: 'validated', change, baseRelease: 'r1', package: { ...skill, checksum: 'hash' }, diff: { added: ['empty/'], modified: ['SKILL.md'], removed: ['old.bin'] } }; return clone(current) },
    install: async (_id, release) => { installs++; assert.equal(release, 'r1'); current.status = 'installed'; return clone(current) },
    cancel: async () => { current.status = 'cancelled'; return clone(current) }
  }
  let notifications = 0
  const view = mount(uploadComponent, { open: true, api, onInstalled: () => { notifications++ } })
  return { ...view, counts: () => ({ puts, installs, creates, notifications }), fail: (v: boolean) => { fail = v } }
}
test('上传真实SFC：原始完整清单上传，新增和同内容一步安装，同名不同内容必须确认', async () => {
  for (const change of ['create', 'identical', 'update'] as const) {
    const view = fixture(change)
    try {
      await drop(view.root); assert.match(text(view.root), /测试技能/); assert.match(text(view.root), /1 个文件 · 1 个目录/)
      await runClick(view.root, '上传并安装')
      assert.equal(view.counts().puts, 1, JSON.stringify(all(view.root).filter(n => n.tag === 'ElAlert').map(n => n.props)))
      if (change === 'update') {
        assert.equal(view.counts().installs, 0); assert.match(text(view.root), /old.bin/)
        await runClick(view.root, '确认更新同名 Skill')
      }
      assert.equal(view.counts().installs, 1); assert.equal(view.counts().notifications, 1)
    } finally { view.close() }
  }
})
test('上传失败可查询持久状态并按同一transfer续传；不混入不同原目录', async () => {
  const view = fixture()
  try {
    await drop(view.root); view.fail(true); await runClick(view.root, '上传并安装')
    assert.equal(view.counts().creates, 1)
    await drop(view.root, dirNode('different', [fileNode('SKILL.md')]))
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && String(n.props.title).includes('清单不同')), JSON.stringify(all(view.root).filter(n => n.tag === 'ElAlert').map(n => n.props)))
    await drop(view.root); view.fail(false); await runClick(view.root, '查询当前状态'); await runClick(view.root, '核验并重试上传')
    assert.equal(view.counts().creates, 1); assert.equal(view.counts().installs, 1)
  } finally { view.close() }
})
test('取消上传清除草稿后可拖入新目录，空历史与查询失败明确反馈', async () => {
  const view = fixture('update')
  try {
    await runClick(view.root, '刷新上传状态'); assert.match(text(view.root), /暂无上传记录/)
    await drop(view.root); await runClick(view.root, '上传并安装'); await runClick(view.root, '取消当前上传')
    await drop(view.root, dirNode('next', [fileNode('SKILL.md')]))
    await runClick(view.root, '上传并安装'); assert.equal(view.counts().creates, 2)
  } finally { view.close() }
})
test('删除二次确认可取消，提交固定release/checksum及确认前version，冲突不误报成功', async () => {
  let removed = 0, changed = 0, failure = false
  const api = { ...baseApi(), package: async () => ({ ...skill, rootName: 'root', release: 'r1', checksum: 'checksum', entries: {} }), remove: async (...args: unknown[]) => { removed++; assert.deepEqual(args, ['fixture', 'r1', 'checksum', 7]); if (failure) throw new IdentityError(409, '冲突') } }
  const view = mount(actions, { skill, api, canManage: true, onChanged: () => { changed++ } })
  try {
    accept = false; await runClick(view.root, '删除 Skill'); assert.equal(removed, 0)
    assert.equal(confirmOptions?.confirmButtonText, '确认删除'); assert.equal(confirmOptions?.cancelButtonText, '取消')
    accept = true; failure = true; await runClick(view.root, '删除 Skill'); assert.equal(removed, 1); assert.match(text(view.root), /已变化/); assert.doesNotMatch(text(view.root), /已删除/)
    failure = false; await runClick(view.root, '删除 Skill'); assert.equal(removed, 2); assert.equal(changed, 2); assert.match(text(view.root), /历史冻结版本保留/)
  } finally { accept = true; view.close() }
})
test('删除响应丢失后读回不存在才报已删除；无维护权限不显示删除', async () => {
  let reads = 0, changed = 0
  const api = { ...baseApi(), package: async () => { if (++reads > 1) throw new IdentityError(404, '不存在'); return { ...skill, rootName: 'root', release: 'r1', checksum: 'checksum', entries: {} } }, remove: async () => { throw new IdentityError(0, '响应丢失') } }
  const view = mount(actions, { skill, api, canManage: true, onChanged: () => { changed++ } })
  try { await runClick(view.root, '删除 Skill'); assert.equal(changed, 1); assert.match(text(view.root), /已核实 Skill 已删除/) } finally { view.close() }
  const readonly = mount(actions, { skill, api, canManage: false })
  try { assert.equal(all(readonly.root).some(n => n.tag === 'ElButton' && text(n) === '删除 Skill'), false); assert.match(text(readonly.root), /保存为文件夹/) } finally { readonly.close() }
})
test('目录权限在网络前请求，取消选择完全不导出', async () => {
  chosen = 0; cancelled = true; let reads = 0
  const api = { ...baseApi(), package: async () => { reads++; throw Error('不应请求') } }
  const view = mount(actions, { skill, api, canManage: true })
  try { await runClick(view.root, '保存为文件夹'); assert.equal(chosen, 1); assert.equal(reads, 0); assert.doesNotMatch(text(view.root), /失败/) }
  finally { cancelled = false; view.close() }
})
test('保存失败显示不完整，重试复用根句柄及首次固定版本，不再次请求目录或新版本', async () => {
  parent.children.clear(); chosen = 0
  const folder = await Read.scanFolder(dirNode('saved', [fileNode('SKILL.md'), dirNode('empty', []), fileNode('binary', new Uint8Array([0, 255]))]))
  let packageReads = 0, fileReads = 0, fail = true
  const releases: string[] = []
  const api = { ...baseApi(), package: async () => { packageReads++; return { ...folder, release: 'fixed-r1', checksum: 'hash' } },
    file: async (_id: string, release: string, path: string) => { fileReads++; releases.push(release); if (fail && fileReads === 2) throw Error('网络中断'); return folder.files.get(path)!.arrayBuffer() } }
  const view = mount(actions, { skill, api, canManage: true })
  try {
    await runClick(view.root, '保存为文件夹'); assert.match(text(view.root), /文件夹不完整/)
    fail = false; await runClick(view.root, '核验并重试保存'); assert.match(text(view.root), /全部目录和文件已读回核验/)
    assert.equal(packageReads, 1); assert.equal(chosen, 1); assert.ok(releases.every(release => release === 'fixed-r1'))
    assert.equal((await parent.getDirectoryHandle('saved')).children.size, 3)
  } finally { view.close() }
})
