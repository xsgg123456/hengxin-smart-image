import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import * as Vue from 'vue'
import { identity } from '../src/api/hengxin/identity'
import * as limits from '../src/api/hengxin/limits'
import type { Picture } from '../src/types/hengxin'
import type { useImageUpload } from '../src/views/hengxin/use-image-upload'

// 执行真实上传组合函数；只替换上传服务和可控的浏览器解码器。
const source = readFileSync(new URL('../src/views/hengxin/use-image-upload.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const renderer = Vue.createRenderer<object, object>({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {},
  setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}
})
test('CLI解码期间身份失效即阻断新上传，正常会话仍可上传', async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'Image')
  try {
    for (const reason of ['changed', 'suspended', 'none'] as const) {
      let decoded!: () => void, calls = 0
      class ImageFixture {
        src = ''; naturalWidth = 8; naturalHeight = 6
        decode() { return new Promise<void>(resolve => { decoded = resolve }) }
      }
      Object.defineProperty(globalThis, 'Image', { configurable: true, value: ImageFixture })
      const module = { exports: {} as { useImageUpload: typeof useImageUpload } }
      const files = { uploadFile: async (file: File) => { calls++; return { id: 'saved', name: file.name, url: 'saved' } } }
      const dependencies: Record<string, unknown> = { vue: Vue, '@/api/files': files, '@/api/hengxin/identity': { identity }, '@/api/hengxin/limits': limits }
      new Function('require', 'module', 'exports', code)((name: string) => {
        if (!(name in dependencies)) throw new Error(`unexpected dependency: ${name}`)
        return dependencies[name]
      }, module, module.exports)
      let upload!: ReturnType<typeof useImageUpload>
      const model = Vue.ref<Picture[]>([])
      const app = renderer.createApp(Vue.defineComponent({ setup() {
        upload = module.exports.useImageUpload(model, { mode: 'wallpaper' })
        return () => Vue.h('div')
      } }))
      app.mount({})
      try {
        const pending = upload.add(new File(['image'], 'A.png', { type: 'image/png' }))
        if (reason !== 'none') identity.advance(reason)
        decoded(); await pending
        assert.equal(calls, reason === 'none' ? 1 : 0)
        assert.equal(model.value.length, reason === 'none' ? 1 : 0)
      } finally { app.unmount() }
    }
  } finally {
    if (descriptor) Object.defineProperty(globalThis, 'Image', descriptor)
    else Reflect.deleteProperty(globalThis, 'Image')
  }
})
