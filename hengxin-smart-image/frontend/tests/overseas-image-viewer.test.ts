import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computed, createRenderer, defineComponent, ref } from 'vue'
import { overseasImageCache } from '../src/api/overseas/image-cache'
import { useImageViewer } from '../src/views/overseas/studio/use-image-viewer'
import { useImagePrefetch } from '../src/views/overseas/studio/use-image-prefetch'
import { thumbnailUrl } from '../src/views/overseas/studio/studio-images'
import type { Studio } from '../src/api/overseas/studio'

const renderer = createRenderer<object, object>({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}, setText() {}, setElementText() {} })
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve() }
const picture = (id: string) => ({ id, name: `${id}.png`, url: `/api/overseas/v1/tasks/t/studio/pictures/${id}/content`, width: 1600, height: 1000, turnId: 't', sku: null, archived: false })

test('查看器只为当前图保留Blob URL，切图/关闭释放，重开校验、错误重试及账号清理', async () => {
  const original = globalThis.fetch, calls: string[] = [], errors: unknown[] = []
  let fail = false
  globalThis.fetch = async (url, options) => { calls.push(`${options?.method}:${url}`); return fail ? new Response(null, { status: 404 }) : new Response('full-original', { headers: { ETag: '"v1"', 'Content-Type': 'image/png' } }) }
  overseasImageCache.setIdentity('viewer')
  const images = ref([picture('a'), picture('b'), picture('c')]); let viewer!: ReturnType<typeof useImageViewer>
  const app = renderer.createApp(defineComponent({ setup() { viewer = useImageViewer(computed(() => images.value), reason => errors.push(reason)); return () => null } })); app.mount({})
  try {
    viewer.open(0); await flush(); assert.equal(viewer.visible.value, true); assert.ok(viewer.urlList.value[0].startsWith('blob:'))
    assert.equal(viewer.urlList.value.filter(url => url.startsWith('blob:')).length, 1)
    await viewer.select(1); assert.ok(viewer.urlList.value[1].startsWith('blob:')); assert.equal(viewer.urlList.value.filter(url => url.startsWith('blob:')).length, 1)
    viewer.close(); assert.equal(viewer.visible.value, false); viewer.open(0); await flush()
    assert.equal(calls.filter(call => call === `GET:${images.value[0].url}`).length, 1)
    assert.equal(calls.filter(call => call === `HEAD:${images.value[0].url}`).length, 1)
    fail = true; await viewer.select(2); assert.match(viewer.error.value, /不存在/); assert.equal(errors.length, 1)
    fail = false; await viewer.retry(); assert.ok(viewer.urlList.value[2].startsWith('blob:'))
    viewer.imageError(); assert.match(viewer.error.value, /无法显示/); assert.equal(viewer.viewerKey.value, 1)
    assert.ok(!viewer.urlList.value[2].startsWith('blob:')); await viewer.retry(); assert.ok(viewer.urlList.value[2].startsWith('blob:'))
    overseasImageCache.setIdentity('other'); assert.equal(viewer.visible.value, false); assert.ok(viewer.urlList.value.every(url => !url.startsWith('blob:')))
  } finally { app.unmount(); overseasImageCache.setIdentity(''); globalThis.fetch = original }
})

test('切会话卸载取消旧预取，当前会话聚合成品/图片附件/素材且忽略文档', async () => {
  const original = globalThis.fetch, calls: string[] = [], signals: AbortSignal[] = []
  globalThis.fetch = async (url, options) => { calls.push(String(url)); signals.push(options!.signal!); return new Promise((_resolve, reject) => options!.signal!.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')), { once: true })) }
  overseasImageCache.setIdentity('prefetch')
  const scope = ref('s1'), data = ref<Studio>({ taskId: 't', taskVersion: 1, completed: false, reopened: false, archiveId: null, activeTurnId: null, skills: [], materials: [], turns: [{ id: 't', text: '', skillName: null, reply: null, error: null, status: 'succeeded', jobId: 'j', jobVersion: 1, createdAt: '', pictures: [picture('a'), picture('b'), picture('c')], attachments: [], referencePictures: [] }] })
  const app = renderer.createApp(defineComponent({ setup() { useImagePrefetch(() => scope.value, () => data.value, () => []); return () => null } })); app.mount({})
  try {
    await flush(); assert.equal(calls.length, 2)
    scope.value = 's2'; data.value = { ...data.value!, turns: [] }; await flush()
    assert.ok(signals.every(signal => signal.aborted)); assert.equal(overseasImageCache.stats().queued, 0)
    assert.ok(!calls.some(url => url.includes('/c/')))
    assert.equal(thumbnailUrl(picture('a')), picture('a').url + '?thumbnail=true')
    const attachment = { id: 'upload:a', name: 'a.jpg', contentType: 'image/jpeg', sizeBytes: 5, source: 'upload' as const, url: '/api/overseas/v1/tasks/t/studio/files/a/content' }
    data.value = { ...data.value!, materials: [attachment, { ...attachment, id: 'upload:doc', contentType: 'application/pdf', url: '/document' }] }; await flush()
    assert.ok(calls.includes(attachment.url + '?preview=true')); assert.ok(!calls.includes('/document'))
    assert.equal(thumbnailUrl(attachment), attachment.url + '?preview=true&thumbnail=true')
  } finally { app.unmount(); await flush(); overseasImageCache.setIdentity(''); globalThis.fetch = original }
})
