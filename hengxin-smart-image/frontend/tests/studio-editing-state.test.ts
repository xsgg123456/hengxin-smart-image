import test from 'node:test'
import assert from 'node:assert/strict'
import { annotationDraft } from '../src/views/hengxin/components/annotation/annotation-drafts'
import { clearDraft, disposePrepared, draftFor, forgetDraft, readReference, referenceLabel, removeReference, snapshot, validateDraft, type Reference } from '../src/views/overseas/studio/editing/state'
import type { AnnotationMark } from '../src/views/hengxin/components/annotation/annotation-model'
import { boardLayout } from '../src/views/overseas/studio/editing/board-layout'
import { overseasImageCache } from '../src/api/overseas/image-cache'
const mark = (note = '修正灯罩'): AnnotationMark => ({ id: crypto.randomUUID(), kind: 'rect', note, x: 2, y: 3, width: 30, height: 40, points: [] })
const reference = (): Reference => ({ id: crypto.randomUUID(), name: '实拍.png', file: new File(['image'], '实拍.png', { type: 'image/png' }), url: '', kind: 'product', note: '参考灯罩形状', status: 'ready', error: '' })

test('1/6/12/100张组图均在适应视野内，六张保持批准的三列布局', () => {
  assert.deepEqual(boardLayout(6), { columns: 3, fitZoom: 1 })
  for (const count of [1, 6, 12, 100]) {
    const { columns, fitZoom } = boardLayout(count)
    for (let index = 0; index < count; index++) {
      assert.ok((index % columns * 408 + 384 + 12) * fitZoom <= 1236)
      assert.ok((Math.floor(index / columns) * 356 + 332 + 12) * fitZoom <= 720)
    }
  }
})

test('单图与整组草稿共享标注替换，身份、任务、会话键隔离；首次seed不覆盖在编辑引用', () => {
  const key = JSON.stringify(['user1', 'task1', 'conversation1', 'picture1'])
  annotationDraft(key).marks = [mark()]
  const draft = draftFor(key)
  assert.equal(draft.marks[0].note, '修正灯罩')
  draft.marks = [mark('新的标注')]
  assert.equal(annotationDraft(key).marks[0].note, '新的标注')
  annotationDraft(key).marks = [mark('替换整个数组')]
  assert.equal(draft.marks[0].note, '替换整个数组')
  for (const other of [['user2', 'task1', 'conversation1'], ['user1', 'task2', 'conversation1'], ['user1', 'task1', 'conversation2']]) {
    const otherKey = JSON.stringify([...other, 'picture1'])
    assert.equal(draftFor(otherKey).marks.length, 0); forgetDraft(otherKey)
  }
  draft.references.push(reference())
  assert.equal(draftFor(key, []).references.length, 1)
  forgetDraft(key); assert.equal(draftFor(key).marks.length, 0); assert.equal(draftFor(key).references.length, 0); forgetDraft(key)
})

test('完整标注意见和参考用途校验，不截断多行内容或清空隐藏自定义用途', () => {
  const draft = { marks: [mark(' ')], references: [] as Reference[] }
  assert.match(validateDraft(draft), /每一处/)
  draft.marks = [mark('a'.repeat(3995))]; assert.match(validateDraft(draft), /4000/)
  draft.marks = []; const item = reference(); draft.references.push(item)
  item.kind = ''; assert.match(validateDraft(draft), /用途/)
  item.kind = 'custom'; item.customPurpose = ' '; assert.match(validateDraft(draft), /自定义/)
  item.customPurpose = '参考包装排版\n保留原来的产品'; assert.equal(validateDraft(draft), '')
  assert.equal(referenceLabel('custom', item.customPurpose), item.customPurpose)
  item.note = 'a'.repeat(2001); assert.match(validateDraft(draft), /2000/)
  item.note = '参考边缘'; item.customPurpose = 'a'.repeat(2001); assert.match(validateDraft(draft), /2000/)
  item.kind = 'product'; assert.equal(validateDraft(draft), ''); assert.equal(item.customPurpose.length, 2001)
  item.status = 'loading'; assert.match(validateDraft(draft), /读取/)
  item.status = 'error'; assert.match(validateDraft(draft), /重试/)
})

test('拒绝非图片、空文件和超过20MiB参考图，坏图保持错误状态可重试', async () => {
  const item = reference()
  item.file = new File(['bad'], 'bad.svg', { type: 'image/svg+xml' }); await readReference(item); assert.equal(item.status, 'error')
  item.file = new File([], 'empty.png', { type: 'image/png' }); await readReference(item); assert.match(item.error, /不能为空/)
  item.file = new File([new Uint8Array(20 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' }); await readReference(item); assert.match(item.error, /20 MiB/)
  const previousImage = Object.getOwnPropertyDescriptor(globalThis, 'Image')
  try {
    Object.defineProperty(globalThis, 'Image', { configurable: true, value: class { naturalWidth = 0; naturalHeight = 0; src = ''; decode() { return Promise.reject(Error('坏图')) } } })
    item.file = reference().file; await readReference(item); assert.equal(item.status, 'error'); assert.match(item.error, /坏图/)
    Object.defineProperty(globalThis, 'Image', { configurable: true, value: class { naturalWidth = 10; naturalHeight = 20; src = ''; decode() { return Promise.resolve() } } })
    await readReference(item); assert.equal(item.status, 'ready'); assert.ok(item.url.startsWith('blob:'))
    removeReference({ marks: [], references: [item] }, item); assert.equal(item.url, '')
  } finally { if (previousImage) Object.defineProperty(globalThis, 'Image', previousImage); else Reflect.deleteProperty(globalThis, 'Image') }
})

test('替换和删除取消过期解码写回；关闭核对不回收仍在草稿中的参考图', async () => {
  const previousImage = Object.getOwnPropertyDescriptor(globalThis, 'Image'), previousRevoke = URL.revokeObjectURL
  const pending: (() => void)[] = [], revoked: string[] = []
  try {
    URL.revokeObjectURL = url => { revoked.push(url); previousRevoke(url) }
    Object.defineProperty(globalThis, 'Image', { configurable: true, value: class { naturalWidth = 12; naturalHeight = 18; src = ''; decode() { return new Promise<void>(resolve => pending.push(resolve)) } } })
    const item = reference(), draft = { marks: [], references: [item] }
    const first = readReference(item)
    item.file = new File(['new'], 'new.webp', { type: 'image/webp' }); const second = readReference(item)
    pending[1](); await second; const latest = item.url
    pending[0](); await first; assert.equal(item.url, latest); assert.ok(revoked.length >= 1)
    disposePrepared([{ picture: { id: 'p', name: '原图.png', url: '/original', width: 12, height: 18, turnId: 't', sku: null, archived: false }, marks: [], annotation: '', text: '', draftKey: 'key', references: [item] }]); assert.ok(!revoked.includes(latest))
    const third = readReference(item); removeReference(draft, item); pending[2](); await third
    assert.equal(draft.references.length, 0); assert.equal(item.url, ''); assert.ok(revoked.includes(latest))
    clearDraft(draft)
  } finally { URL.revokeObjectURL = previousRevoke; if (previousImage) Object.defineProperty(globalThis, 'Image', previousImage); else Reflect.deleteProperty(globalThis, 'Image') }
})

test('材料快照使用鉴权原图实际尺寸导出PNG，冻结意见且不替换原图URL，权限失败不中途伪成功', async () => {
  const descriptors = ['Image', 'document'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)] as const)
  const oldFetch = globalThis.fetch, key = 'snapshot-test', calls: RequestInit[] = []
  const canvas = { width: 0, height: 0, getContext: () => ({ drawImage() {}, strokeRect() {}, beginPath() {}, arc() {}, fill() {}, fillText() {} }), toBlob(callback: (blob: Blob) => void, type: string) { assert.equal(type, 'image/png'); callback(new Blob(['png'], { type })) } }
  const picture = { id: 'original', name: '原图.jpg', url: '/authorized-original', width: 120, height: 160, turnId: 'turn', sku: null, archived: false }
  try {
    overseasImageCache.setIdentity('editing-test')
    globalThis.fetch = async (_url, options) => { calls.push(options || {}); return new Response(new Blob(['jpeg'], { type: 'image/jpeg' }), { headers: { 'Content-Type': 'image/jpeg' } }) }
    Object.defineProperty(globalThis, 'Image', { configurable: true, value: class { naturalWidth = 1200; naturalHeight = 1600; src = ''; decode() { return Promise.resolve() } } })
    Object.defineProperty(globalThis, 'document', { configurable: true, value: { createElement: () => canvas } })
    const draft = draftFor(key); draft.marks = [mark('保留灯罩纹理')]
    const result = await snapshot(picture, key, new AbortController().signal)
    assert.equal(result.file?.type, 'image/png'); assert.equal(canvas.width, 1200); assert.equal(canvas.height, 1600)
    assert.equal(result.picture.url, picture.url); assert.ok(result.annotation.startsWith('blob:')); assert.ok(result.originalPreview?.startsWith('blob:'))
    assert.equal(calls[0].credentials, 'include'); assert.equal(calls[0].redirect, 'error')
    draft.marks[0].note = '继续编辑后的意见'; assert.match(result.text, /保留灯罩纹理/); assert.equal(result.marks[0].note, '保留灯罩纹理')
    disposePrepared([result])
    globalThis.fetch = async () => new Response('', { status: 403 })
    await assert.rejects(snapshot({ ...picture, url: '/denied' }, key, new AbortController().signal), /暂无权限/)
  } finally {
    forgetDraft(key); overseasImageCache.setIdentity(''); globalThis.fetch = oldFetch
    for (const [name, descriptor] of descriptors) { if (descriptor) Object.defineProperty(globalThis, name, descriptor); else Reflect.deleteProperty(globalThis, name) }
  }
})
