import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createDraft } from '../src/views/hengxin/api-image-edits/real-draft'
import { ApiError } from '../src/api/hengxin/http'
import type { ApiPicture, ApiTaskInput } from '../src/types/api-image-edits'
const file = (name: string) => new File(['image'], name, { type: 'image/png' })
const flush = () => new Promise(resolve => setTimeout(resolve, 0))
const urls = { createObjectURL: (blob: Blob) => `blob:${(blob as File).name}`, revokeObjectURL: (_url: string) => {} } as typeof URL
function setup() {
  const uploads = new Map<string, (p: ApiPicture) => void>()
  const calls: { input: ApiTaskInput; key: string }[] = [], deleted: string[] = []
  let fail = true, key = 0
  const draft = createDraft({
    upload: f => new Promise(resolve => uploads.set(f.name, resolve)),
    deleteFile: async id => { deleted.push(id) },
    create: async (input, key) => { calls.push({ input, key }); if (fail) throw new ApiError('UNAVAILABLE', '连接断开'); return { taskId: 'task' } }
  }, async () => {}, urls, () => `key-${++key}`)
  return { draft, uploads, calls, deleted, succeed: () => { fail = false } }
}
test('上传按选择顺序占位，完成倒序与切换页面不绕过未完成阻塞', async () => {
  const { draft, uploads } = setup()
  draft.state.name = '任务'; draft.state.prompt = '要求'; draft.add(file('original')); draft.add(file('material'))
  await flush()
  uploads.get('material')!({ name: 'material', url: 'm', fileId: 'm' }); await flush()
  assert.deepEqual(draft.state.images.map(p => p.name), ['original', 'material']); assert.equal(draft.valid(), false)
  assert.equal(await draft.submit(), undefined)
  uploads.get('original')!({ name: 'original', url: 'o', fileId: 'o' }); await flush()
  assert.equal(draft.valid(), true)
})
test('提交断网锁定输入，原请求键和快照保留，确认后清空草稿', async () => {
  const { draft, uploads, calls, succeed } = setup()
  draft.state.name = '任务'; draft.state.prompt = '要求'; draft.add(file('o')); draft.add(file('m')); await flush()
  for (const [name, resolve] of uploads) resolve({ name, url: name, fileId: name })
  await flush(); await draft.submit()
  assert.equal(draft.locked(), true); draft.move(0, 1); draft.add(file('ignored')); await draft.remove(draft.state.images[0])
  assert.equal(draft.state.images.length, 2); assert.equal(draft.state.images[0].name, 'o')
  succeed(); assert.equal(await draft.submit(), 'task')
  assert.equal(calls[0].key, calls[1].key); assert.deepEqual(calls[0].input, calls[1].input)
  assert.deepEqual(calls[0].input.originalFileIds, ['o']); assert.equal(calls[0].input.materialFileId, 'm')
  assert.equal(draft.state.images.length, 0); assert.equal(draft.locked(), false)
})
test('解码失败不上传；移除已上传图片清理专属文件', async () => {
  let uploadCalls = 0
  const failed = createDraft({ upload: async () => { uploadCalls++; throw new Error('unexpected') }, deleteFile: async () => {}, create: async () => ({ taskId: 'x' }) }, async () => { throw new Error('无法解码') }, urls)
  failed.add(file('broken')); await flush()
  assert.equal(uploadCalls, 0); assert.equal(failed.state.images[0].state, 'failed'); assert.match(failed.state.images[0].error, /无法解码/)
  const { draft, uploads, deleted } = setup(); draft.add(file('valid')); await flush()
  uploads.get('valid')!({ fileId: 'saved', name: 'valid', url: 'v' }); await flush()
  await draft.remove(draft.state.images[0]); assert.deepEqual(deleted, ['saved']); assert.equal(draft.state.images.length, 0)
})
test('首次响应未知后认证过期仍保留原键；确定性输入拒绝允许修改', async () => {
  const keys: string[] = []; let count = 0
  const draft = createDraft({ upload: async f => ({ name: f.name, url: f.name, fileId: f.name }), deleteFile: async () => {}, create: async (_input, key) => {
    keys.push(key); count++
    if (count === 1) throw new ApiError('UNAVAILABLE', '响应丢失')
    if (count === 2) throw new ApiError('AUTH', '认证过期', 401)
    return { taskId: 'confirmed' }
  } }, async () => {}, urls)
  draft.state.name = '任务'; draft.state.prompt = '要求'; draft.add(file('o')); draft.add(file('m')); await flush()
  await draft.submit(); await draft.submit(); assert.equal(draft.locked(), true)
  assert.equal(await draft.submit(), 'confirmed'); assert.equal(new Set(keys).size, 1)
})
test('刷新恢复未确认提交快照并用原键确认，不重复生成新请求', async () => {
  type Saved = { key: string; input: ApiTaskInput; uncertain: boolean }
  let stored: Saved | null = null
  const persistence = { load: () => stored, save: (value: Saved | null) => { stored = value ? structuredClone(JSON.parse(JSON.stringify(value))) as Saved : null } }
  const keys: string[] = []; let offline = true
  const api = { upload: async (f: File) => ({ name: f.name, url: f.name, fileId: f.name }), deleteFile: async () => {}, create: async (_input: ApiTaskInput, key: string) => {
    keys.push(key); if (offline) throw new ApiError('UNAVAILABLE', '响应丢失'); return { taskId: 'saved-task' }
  } }
  const original = createDraft(api, async () => {}, urls, () => 'original-key', persistence)
  original.state.name = '任务'; original.state.prompt = '要求'; original.add(file('o')); original.add(file('m')); await flush(); await original.submit()
  const restored = createDraft(api, async () => {}, urls, () => 'new-key-must-not-be-used', persistence)
  assert.equal(restored.locked(), true); assert.equal(restored.state.name, '任务')
  offline = false; assert.equal(await restored.submit(), 'saved-task'); assert.deepEqual(keys, ['original-key', 'original-key']); assert.equal(stored, null)
})
