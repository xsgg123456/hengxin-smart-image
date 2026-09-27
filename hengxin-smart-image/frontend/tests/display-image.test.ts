import assert from 'node:assert/strict'
import test from 'node:test'
import { displayImageUrl } from '../src/views/hengxin/display-image'

test('display URLs retain version and only transform private content endpoints', () => {
  const original = '/api/v1/files/12345678-abcd/content?version=2'
  assert.equal(displayImageUrl(original), original + '&variant=256')
  assert.equal(displayImageUrl(original, 1024), original + '&variant=1024')
  assert.equal(displayImageUrl('/api/v1/api-image-edits/files/abcd/content'), '/api/v1/api-image-edits/files/abcd/content?variant=256')
  for (const url of ['blob:123', 'data:image/png;base64,test', 'https://example.com/image.png', original + '&download=true']) {
    assert.equal(displayImageUrl(url), url)
  }
})
