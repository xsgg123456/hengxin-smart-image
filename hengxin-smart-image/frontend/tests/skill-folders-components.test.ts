import test from 'node:test'
import assert from 'node:assert/strict'
import * as Transfers from '../src/api/overseas/skill-transfers'
import * as Read from '../src/views/shared/skills/skill-folder-read'
import * as Save from '../src/views/shared/skills/skill-folder-save'
import * as Zip from '../src/views/shared/skills/skill-folder-zip'
import * as Management from '../src/api/overseas/management'
import { formatAttachmentSize } from '../src/api/overseas/attachment-download'
import { OVERSEAS_PLATFORMS } from '../src/views/overseas/platforms'
import { IdentityError } from '../src/api/identity/request'
import { all, click, compile, flush, mount, simple, table, text, type Node } from './membership-test-harness'
import { dirNode, fileNode, MemoryDirectory } from './skill-folders-fixture'
const uploadComponent = compile('views/shared/skills/SkillFolderUpload.vue', { '@/api/shared/skill-transfers': Transfers, './skill-folder-read': Read })
Object.assign(uploadComponent, { components: { ElTree: simple('ElTree'), ElProgress: simple('ElProgress') } })
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
let accept = true, chosen = 0, cancelled = false, confirmMessage = '', confirmOptions: Record<string, unknown> | undefined
const parent = new MemoryDirectory('Downloads')
const actions = compile('views/shared/skills/SkillFolderActions.vue', {
  '@/api/shared/skill-transfers': Transfers, '@/api/identity/request': { IdentityError },
  '@/utils/attachment-size': { formatAttachmentSize },
  './skill-folder-save': { ...Save, supportsDirectorySave: () => true, chooseParent: () => { chosen++; if (cancelled) return Promise.reject(new DOMException('cancel', 'AbortError')); return Promise.resolve(parent) } },
  './skill-folder-zip': Zip,
  'element-plus': { ElMessageBox: { confirm: async (message: string, _title: string, options: Record<string, unknown>) => { confirmMessage = message; confirmOptions = options; if (!accept) throw Error('cancel') } } }
})
const skill = { id: 'fixture', name: 'fixture', displayName: '测试技能', description: '说明', version: 7, enabled: false, platforms: [] }
const baseApi = () => Transfers.createSkillTransferApi(async () => { throw Error('不应请求真实API') })

test('国内上传复用真实弹窗并提示绑定工作台，海外原文不变', () => {
  const domestic = mount(uploadComponent, { open: true, api: baseApi(), domestic: true })
  const overseas = mount(uploadComponent, { open: true, api: baseApi() })
  try {
    assert.match(text(domestic.root), /新增默认关闭且未绑定工作台/)
    assert.doesNotMatch(text(domestic.root), /未分配平台/)
    assert.match(text(overseas.root), /新增默认关闭且未分配平台/)
  } finally { domestic.close(); overseas.close() }
})

test('国内目录的真实操作组件显示并触发启用或停用，保存时禁用', async () => {
  const catalog = compile('views/shared/skills/OverseasSkillCatalog.vue', {
    '@/components/core/tables/art-table/index.vue': { default: table, __esModule: true },
    './SkillFolderActions.vue': { default: actions, __esModule: true },
    './platforms': { OVERSEAS_PLATFORMS }, './OverseasSkillPlatformsDialog.vue': { default: simple('Dialog'), __esModule: true },
    'element-plus': { ElMessageBox: {} }
  })
  for (const enabled of [true, false]) {
    const events: string[] = []
    const view = mount(catalog, { skills: [{ ...skill, enabled }], managed: true, domestic: true,
      transferApi: baseApi(), canToggle: true, onToggle: (id: string) => events.push(id) })
    try {
      await runClick(view.root, enabled ? '停用' : '启用')
      assert.deepEqual(events, ['fixture'])
      assert.match(text(view.root), /下载 ZIP/)
      assert.match(text(view.root), /删除/)
    } finally { view.close() }
  }
  const saving = mount(catalog, { skills: [skill], managed: true, domestic: true,
    transferApi: baseApi(), canToggle: true, savingId: 'fixture' })
  try {
    const toggle = all(saving.root).find(n => n.tag === 'ElButton' && text(n) === '启用')
    assert.equal(toggle?.props.disabled, true)
  } finally { saving.close() }
})
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
  const api = { ...baseApi(), package: async () => ({ ...skill, rootName: 'root', release: 'r1', checksum: 'checksum', entries: {} }), remove: async (...args: unknown[]) => { removed++; assert.deepEqual(args, ['fixture', 'r1', 'checksum', 7]); if (failure) throw new IdentityError(409, '冲突', '仍有运行中的任务使用此 Skill，请稍后重试'); return { deleted: true, release: 'r2', reclaimedBytes: 6_570_000_000 } } }
  const view = mount(actions, { skill, api, canManage: true, onChanged: () => { changed++ } })
  try {
    accept = false; await runClick(view.root, '删除 Skill'); assert.equal(removed, 0)
    assert.equal(confirmOptions?.confirmButtonText, '确认删除'); assert.equal(confirmOptions?.cancelButtonText, '取消')
    assert.match(confirmMessage, /永久删除/); assert.match(confirmMessage, /历史会话资料保留/); assert.match(confirmMessage, /排队中或运行中/)
    accept = true; failure = true; await runClick(view.root, '删除 Skill'); assert.equal(removed, 1); assert.match(text(view.root), /仍有运行中的任务使用此 Skill/); assert.doesNotMatch(text(view.root), /已删除/)
    failure = false; await runClick(view.root, '删除 Skill'); assert.equal(removed, 2); assert.equal(changed, 2); assert.match(text(view.root), /Skill 已删除，释放 6570.0 MB/)
  } finally { accept = true; view.close() }
})
test('删除响应丢失不推断成功，原请求可重试且如实显示零释放；无维护权限不显示删除', async () => {
  let reads = 0, changed = 0
  let calls = 0
  const api = { ...baseApi(), package: async () => { if (++reads > 1) throw new IdentityError(404, '不存在'); return { ...skill, rootName: 'root', release: 'r1', checksum: 'checksum', entries: {} } }, remove: async (...args: unknown[]) => { assert.deepEqual(args, ['fixture', 'r1', 'checksum', 7]); if (++calls === 1) throw new IdentityError(0, '响应丢失'); return { deleted: true, release: 'r2', reclaimedBytes: 0 } } }
  const view = mount(actions, { skill, api, canManage: true, onChanged: () => { changed++ } })
  try {
    await runClick(view.root, '删除 Skill'); assert.equal(changed, 0); assert.match(text(view.root), /响应丢失/); assert.doesNotMatch(text(view.root), /已删除/)
    await runClick(view.root, '删除 Skill'); assert.equal(changed, 1); assert.equal(reads, 1); assert.match(text(view.root), /Skill 已删除，释放 0 B/)
  } finally { view.close() }
  const readonly = mount(actions, { skill, api, canManage: false })
  try { assert.equal(all(readonly.root).some(n => n.tag === 'ElButton' && text(n) === '删除 Skill'), false); assert.match(text(readonly.root), /保存为文件夹/) } finally { readonly.close() }
})

test('删除API仅接受已完成且回收字节为非负安全整数的响应', async () => {
  for (const reclaimedBytes of [0, 6_570_000_000]) {
    const result = { deleted: true, release: 'r2', reclaimedBytes }
    const api = Transfers.createSkillTransferApi(async () => Response.json(result))
    assert.deepEqual(await api.remove('s', 'r1', 'checksum', 7), result)
  }
  for (const result of [{ deleted: false, release: 'r2', reclaimedBytes: 0 }, { deleted: true, release: 'r2' }, { deleted: true, release: 'r2', reclaimedBytes: -1 }, { deleted: true, release: 'r2', reclaimedBytes: 1.5 }]) {
    const api = Transfers.createSkillTransferApi(async () => Response.json(result))
    await assert.rejects(api.remove('s', 'r1', 'checksum', 7), /响应格式错误/)
  }
})

test('清理失败后目录503保留真实行与原删除请求，重试成功后目录移除仍显示回收量', async () => {
  const catalog = compile('views/shared/skills/OverseasSkillCatalog.vue', {
    '@/components/core/tables/art-table/index.vue': { default: table, __esModule: true },
    './SkillFolderActions.vue': { default: actions, __esModule: true },
    './platforms': { OVERSEAS_PLATFORMS }, './OverseasSkillPlatformsDialog.vue': { default: simple('Dialog'), __esModule: true },
    'element-plus': { ElMessageBox: {} }
  })
  const live = compile('views/shared/skills/OverseasLiveSkills.vue', {
    '@/api/shared/skill-transfers': Transfers, './SkillFolderUpload.vue': { default: simple('Upload'), __esModule: true },
    '@/api/shared/skill-types': Management, '@/api/identity/request': { IdentityError },
    './OverseasSkillCatalog.vue': { default: catalog, __esModule: true }
  })
  let pending = false, removed = false, reads = 0, deletes = 0
  const api = { skills: async () => { if (pending) throw new IdentityError(503, '清理未完成，请重试删除'); return { items: removed ? [] : [skill], canToggle: true, canManagePlatforms: true } } }
  const transferApi = { ...baseApi(), package: async () => { reads++; assert.equal(pending, false); return { ...skill, rootName: 'root', release: 'r1', checksum: 'checksum', entries: {} } },
    remove: async (...args: unknown[]) => {
      assert.deepEqual(args, ['fixture', 'r1', 'checksum', 7])
      if (++deletes === 1) { pending = true; throw new IdentityError(503, '清理失败', '清理失败，请重试删除') }
      pending = false; removed = true; return { deleted: true, release: 'r2', reclaimedBytes: 1_500_000 }
    } }
  const view = mount(live, { api, transferApi }); await flush()
  try {
    await runClick(view.root, '删除 Skill'); assert.match(text(view.root), /清理失败，请重试删除/); assert.doesNotMatch(text(view.root), /已删除/)
    await runClick(view.root, '刷新 Skill')
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && String(n.props.title).includes('清理未完成')))
    assert.match(text(view.root), /测试技能/)
    assert.equal(all(view.root).find(n => n.tag === 'ElButton' && text(n) === '删除 Skill')?.props.disabled, false)
    await runClick(view.root, '删除 Skill'); assert.equal(reads, 1); assert.equal(deletes, 2)
    assert.doesNotMatch(text(view.root), /测试技能/)
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && n.props.title === 'Skill 已删除，释放 1.5 MB'))
  } finally { view.close() }
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
