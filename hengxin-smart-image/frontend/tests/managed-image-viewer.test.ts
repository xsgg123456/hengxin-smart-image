import test from 'node:test'
import assert from 'node:assert/strict'
import { computed, createRenderer, defineComponent, nextTick, ref } from 'vue'
import { useImageViewer } from '../src/views/shared/studio/use-image-viewer'
import { managedImageAccess, downloadManagedAsset } from '../src/views/hengxin/admin/workspace-sessions/managed-image-access'
import { IdentityError } from '../src/api/identity/request'

const renderer = createRenderer<object, object>({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}, setText() {}, setElementText() {} })
const asset = (id: string) => ({ id, name: `${id}.png`, contentType: 'image/png', sizeBytes: 12, url: `/api/v1/management/domestic-studio/sessions/s/pictures/${id}/content` })
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }

test('管理预览逐次GET核权、切图和关闭回收URL、失败重试及会话卸载拒绝迟到图', async () => {
  const originalFetch = globalThis.fetch, create = URL.createObjectURL, revoke = URL.revokeObjectURL
  const calls: { url: string; signal: AbortSignal }[] = [], allocated: string[] = [], released: string[] = [], errors: unknown[] = []
  let status = 200, hold = false, resolveHeld: ((value: Response) => void) | undefined
  URL.createObjectURL = blob => { const url = create(blob); allocated.push(url); return url }
  URL.revokeObjectURL = url => { released.push(url); revoke(url) }
  globalThis.fetch = async (url, options) => {
    assert.equal(options?.method, undefined); assert.equal(options?.cache, 'no-store'); assert.equal(options?.redirect, 'error'); assert.equal(options?.credentials, 'include')
    calls.push({ url: String(url), signal: options!.signal! })
    return hold ? new Promise(resolve => { resolveHeld = resolve }) : new Response('image', { status })
  }
  const images = ref([asset('a'), asset('b')]); let viewer!: ReturnType<typeof useImageViewer>
  const app = renderer.createApp(defineComponent({ setup() { viewer = useImageViewer(computed(() => images.value), reason => errors.push(reason), managedImageAccess); return () => null } })); app.mount({})
  try {
    const thumbnail = await managedImageAccess.thumbnail(images.value[0], new AbortController().signal)
    assert.match(calls.at(-1)!.url, /\?thumbnail=true$/); thumbnail.release()
    viewer.open(0); await flush(); const first = viewer.urlList.value[0]; assert.match(first, /^blob:/)
    await viewer.select(1); assert.ok(released.includes(first)); assert.equal(viewer.urlList.value.filter(url => url.startsWith('blob:')).length, 1)
    viewer.close(); assert.deepEqual(new Set(released), new Set(allocated))
    viewer.open(0); await flush(); assert.equal(calls.filter(call => call.url === asset('a').url).length, 2)
    status = 403; await viewer.select(1); assert.ok(errors[0] instanceof IdentityError); assert.match(viewer.error.value, /撤销/)
    status = 200; await viewer.retry(); assert.match(viewer.urlList.value[1], /^blob:/)
    images.value = [asset('c')]; await flush(); assert.equal(viewer.visible.value, false)
    hold = true; viewer.open(0); await flush(); const pending = calls.at(-1)!, before = allocated.length
    app.unmount(); assert.equal(pending.signal.aborted, true)
    resolveHeld!(new Response('late')); await flush(); assert.equal(allocated.length, before)
    assert.deepEqual(new Set(released), new Set(allocated)); assert.equal(errors.length, 1)
  } finally { app.unmount(); globalThis.fetch = originalFetch; URL.createObjectURL = create; URL.revokeObjectURL = revoke }
})

test('管理图片下载使用原件GET且拒绝其他作用域和中止响应', async () => {
  const originalFetch = globalThis.fetch
  let calls = 0
  globalThis.fetch = async () => { calls++; return new Response('image') }
  try {
    await assert.rejects(() => managedImageAccess.load({ ...asset('a'), url: '/api/overseas/v1/tasks/t/studio/pictures/a/content' }, new AbortController().signal), /地址无效/)
    assert.equal(calls, 0)
    const controller = new AbortController(); controller.abort()
    await assert.rejects(() => downloadManagedAsset(asset('a'), controller.signal), /abort/i)
  } finally { globalThis.fetch = originalFetch }
})
