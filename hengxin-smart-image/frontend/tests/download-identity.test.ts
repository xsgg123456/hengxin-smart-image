import test from 'node:test'
import assert from 'node:assert/strict'
import { identity, StaleIdentityError } from '../src/api/hengxin/identity'
import * as helpers from '../src/views/hengxin/download-helpers'
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

