import test from 'node:test'
import assert from 'node:assert/strict'
import { prepareStudioDownload } from '../src/api/overseas/studio-download'
import { createImageCache } from '../src/api/overseas/image-cache'
import { compile, mount, click, all, simple, flush } from './membership-test-harness'
import { emptyTaskDraft } from '../src/api/overseas/tasks'
import * as Languages from '../src/views/overseas/languages'
import { OVERSEAS_PLATFORMS } from '../src/views/overseas/platforms'
import * as types from '../src/views/overseas/types'
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD1sAAAAASUVORK5CYII=', 'base64')
const pictures = ['a', 'b'].map(id => ({ id, name: '同名.png', url: `/api/overseas/v1/tasks/t/studio/pictures/${id}/content` }))
const signal = () => new AbortController().signal
function entries(bytes: Buffer) {
  const files: { name: string; data: Buffer }[] = []; let offset = 0
  while (bytes.readUInt32LE(offset) === 0x04034b50) {
    const length = bytes.readUInt16LE(offset + 26), size = bytes.readUInt32LE(offset + 18), start = offset + 30 + length
    files.push({ name: bytes.subarray(offset + 30, start).toString(), data: bytes.subarray(start, start + size) }); offset = start + size
  }
  return files
}
test('所选图片按鉴权原图获取，部分/全部ZIP保留原始字节且同名不覆盖', async () => {
  const requested: string[] = []
  const cache = createImageCache({ fetcher: async (url, options) => {
    requested.push(String(url)); assert.equal(options?.credentials, 'include'); assert.equal(options?.redirect, 'error')
    return new Response(png, { headers: { 'Content-Type': 'image/png' } })
  } })
  cache.setIdentity('test-account')
  for (const selected of [pictures.slice(1), pictures]) {
    const zip = await prepareStudioDownload(selected, signal(), cache)
    const files = entries(Buffer.from(await zip.arrayBuffer()))
    assert.equal(files.length, selected.length); assert.equal(new Set(files.map(f => f.name)).size, selected.length)
    for (const file of files) assert.deepEqual(file.data, png)
  }
  assert.ok(requested.every(url => !url.includes('?'))); assert.equal(requested[0], pictures[1].url)
  cache.clear()
})
test('空选/外部地址/读取失败/取消不产出残缺ZIP', async () => {
  const cache = createImageCache({ fetcher: async url => String(url).includes('/a/') ? new Response(png, { headers: { 'Content-Type': 'image/png' } }) : new Response(null, { status: 403 }) })
  cache.setIdentity('test-account')
  await assert.rejects(prepareStudioDownload([], signal(), cache), /请选择/)
  await assert.rejects(prepareStudioDownload([{ ...pictures[0], url: 'https://example.com/a.png' }], signal(), cache), /地址无效/)
  await assert.rejects(prepareStudioDownload(pictures, signal(), cache), /权限/)
  const controller = new AbortController(); controller.abort()
  await assert.rejects(prepareStudioDownload(pictures, controller.signal, cache), /abort/i)
  cache.clear()
})
test('下载按钮空选禁用，忙碌防重复，失败可重试，卸载不触发保存', async () => {
  let calls = 0, finish!: (blob: Blob) => void, saves = 0; const failures: unknown[] = []
  const component = compile('views/overseas/studio/StudioDownload.vue', {
    '@/api/overseas/studio-download': { prepareStudioDownload: () => { calls++; return new Promise<Blob>(resolve => { finish = resolve }) } },
    '@/api/overseas/pictures': { saveBlob: () => saves++ }
  })
  const empty = mount(component, { pictures: [] }); assert.equal(all(empty.root).find(n => n.tag === 'ElButton')!.props.disabled, true); empty.close()
  const view = mount(component, { pictures, onFailure: (e: unknown) => failures.push(e) })
  click(view.root, '下载所选图片（2）'); click(view.root, '下载所选图片（2）'); await flush()
  assert.equal(calls, 1); assert.equal(all(view.root).find(n => n.tag === 'ElButton')!.props.loading, true)
  view.close(); finish(new Blob(['zip'])); await flush(); assert.equal(saves, 0); assert.equal(failures.length, 0)
  let attempts = 0
  const retry = compile('views/overseas/studio/StudioDownload.vue', {
    '@/api/overseas/studio-download': { prepareStudioDownload: async () => { if (++attempts === 1) throw Error('失败'); return new Blob(['zip']) } },
    '@/api/overseas/pictures': { saveBlob: () => saves++ }
  })
  const retried = mount(retry, { pictures, onFailure: (e: unknown) => failures.push(e) })
  click(retried.root, '下载所选图片（2）'); await flush(); assert.equal(failures.length, 1); assert.equal(saves, 0)
  click(retried.root, '下载所选图片（2）'); await flush(); assert.equal(saves, 1); retried.close()
})
test('图需表单保持默认及历史值，平台顺序与品牌下拉按要求', () => {
  const component = compile('views/overseas/OverseasCreate.vue', { './languages': Languages, './platforms': { OVERSEAS_PLATFORMS }, './types': types })
  Object.assign(component, { components: { ElStep: simple('ElStep'), ElSteps: simple('ElSteps') } })
  const draft = emptyTaskDraft(); assert.equal(draft.brand, ''); assert.equal(draft.platform, '')
  for (const legacy of [false, true]) {
    const modelValue = legacy ? { ...draft, platform: '旧平台', brand: '旧品牌' } : draft
    const view = mount(component, { modelValue, allowed: true })
    const items = all(view.root).filter(n => n.tag === 'ElFormItem')
    const field = (label: string) => items.find(n => n.props.label === label)!
    assert.equal(all(field('任务名称')).find(n => n.tag === 'ElInput')!.props.placeholder, undefined)
    assert.deepEqual(all(field('目标平台')).filter(n => n.tag === 'ElOption').map(n => n.props.value), ['Amazon','Wayfair','Mercado Libre','Walmart','The Home Depot','Shopee', ...(legacy ? ['旧平台'] : [])])
    assert.equal(all(field('品牌')).some(n => n.tag === 'ElInput'), false)
    assert.deepEqual(all(field('品牌')).filter(n => n.tag === 'ElOption').map(n => n.props.value), ['OUTON','OUTONLIFE','BELEEV', ...(legacy ? ['旧品牌'] : [])])
    assert.equal(modelValue.brand, legacy ? '旧品牌' : ''); view.close()
  }
})
