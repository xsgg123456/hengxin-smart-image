import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { identity, StaleIdentityError } from '../src/api/hengxin/identity'
import * as helpers from '../src/views/hengxin/download-helpers'
import type * as downloads from '../src/views/hengxin/download'
const png = new Uint8Array(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD1sAAAAASUVORK5CYII=', 'base64'))
const id = '11111111-1111-4111-8111-111111111111'
const flush = () => new Promise(resolve => setImmediate(resolve))
function delayedBlob(zipped: boolean) {
  const blob = zipped ? helpers.buildZip([{ name: 'a.png', data: png }]) : new Blob([png], { type: 'image/png' })
  let release!: () => void
  const part = zipped ? blob.slice(-22) : blob
  const original = part.arrayBuffer.bind(part)
  part.arrayBuffer = () => new Promise<ArrayBuffer>(resolve => { release = () => { void original().then(resolve) } })
  if (zipped) blob.slice = () => part
  return { blob, release: () => release() }
}
test('图片及ZIP正文读完后的异步格式校验，换号/隐藏均拒绝旧Blob', async () => {
  const original = globalThis.fetch
  try {
    for (const zipped of [false, true]) for (const reason of ['changed', 'suspended'] as const) {
      const pending = delayedBlob(zipped)
      globalThis.fetch = async () => { const response = new Response(null); response.blob = async () => pending.blob; return response }
      const download = helpers.requestDownload('/api', [id], zipped ? 'set' : undefined)
      await flush(); identity.advance(reason); pending.release()
      await assert.rejects(download, StaleIdentityError)
    }
  } finally { globalThis.fetch = original }
})

test('真实下载入口在最终校验后再核验身份，不触发旧文件保存或旧错误提示', async () => {
  const source = readFileSync(new URL('../src/views/hengxin/download.ts', import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_API_URL', 'undefined')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  let saves = 0, errors = 0
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
  Object.defineProperty(globalThis, 'document', { configurable: true, value: {
    body: { append() {} }, createElement: () => ({ href: '', download: '', click() { saves++ }, remove() {} })
  } })
  try {
    for (const reason of ['changed', 'suspended'] as const) {
      const pending = delayedBlob(false)
      const module = { exports: {} as typeof downloads }
      const dependencies: Record<string, unknown> = {
        'element-plus': { ElMessage: { error() { errors++ } } },
        '@/api/hengxin/client': { isMockMode: false }, '@/api/hengxin/identity': { identity },
        './download-helpers': { ...helpers, requestDownload: async () => pending.blob }
      }
      new Function('require', 'module', 'exports', code)((name: string) => {
        if (!(name in dependencies)) throw new Error(`unexpected dependency: ${name}`)
        return dependencies[name]
      }, module, module.exports)
      const operation = module.exports.downloadPicture({ name: 'A.png', url: '/a', fileId: id })
      await flush(); identity.advance(reason); pending.release(); await operation
    }
    assert.equal(saves, 0); assert.equal(errors, 0)
  } finally {
    if (original) Object.defineProperty(globalThis, 'document', original)
    else Reflect.deleteProperty(globalThis, 'document')
  }
})
