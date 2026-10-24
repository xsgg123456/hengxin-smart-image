import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h } from 'vue'
import { checkImage, imageUrl, isImage } from '../src/views/overseas/studio/studio-images'
import { downloadAttachment } from '../src/api/overseas/attachment-download'
import { all, compile, flush, mount, text } from './membership-test-harness'

test('缩略图预览检查失败后，实际图片组件仍按原件地址独立下载', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
  const requests: string[] = [], downloads: string[] = []
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { body: { appendChild() {} }, createElement: () => ({ href: '', download: '', click() { downloads.push(this.href) }, remove() {} }) } })
  const asset = { id: 'upload:a', name: '损坏预览.jpg', contentType: 'image/jpeg', sizeBytes: 100, url: '/api/overseas/v1/tasks/task/studio/files/a/content', source: 'upload' }
  const fetcher: typeof fetch = async (url, options) => { requests.push(String(url)); assert.equal(options?.method, 'HEAD'); return new Response(null, { status: String(url).includes('preview=true') ? 503 : 200 }) }
  const component = compile('views/overseas/studio/StudioAssetImage.vue', {
    './studio-images': { imageUrl, isImage, checkImage: (...args: Parameters<typeof checkImage>) => checkImage(args[0], args[1], fetcher) },
    '@/api/overseas/attachment-download': { downloadAttachment: (...args: Parameters<typeof downloadAttachment>) => downloadAttachment(args[0], args[1], args[2], fetcher) }
  })
  Object.assign(component, { components: { ElImage: defineComponent({ setup(_props, { attrs, slots }) { return () => h('image', attrs, slots.error?.()) } }) } })
  const view = mount(component, { asset, group: [asset], title: '图片' })
  try {
    const image = all(view.root).find(item => item.tag === 'image')!
    ;(image.props.onError as () => void)(); await flush()
    assert.deepEqual(requests, [`${asset.url}?preview=true`])
    const button = all(view.root).find(item => item.tag === 'button' && text(item) === '下载原文件')!
    ;(button.props.onClick as (event: unknown) => void)({ stopPropagation() {} }); await flush()
    assert.deepEqual(requests, [`${asset.url}?preview=true`, asset.url]); assert.deepEqual(downloads, [asset.url])
  } finally { view.close(); if (original) Object.defineProperty(globalThis, 'document', original); else Reflect.deleteProperty(globalThis, 'document') }
})
