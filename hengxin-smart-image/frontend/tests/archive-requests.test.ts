import test from 'node:test'
import assert from 'node:assert/strict'
import { createArchiveRequests } from '../src/views/hengxin/archive-requests'
import type { Archive } from '../src/types/hengxin'

const result: Archive = { id: 'a', name: '成品', mode: 'text', images: [], time: 'now', ownerId: 'u', imageVersionIds: ['v1'] }
test('lost archive response replays original snapshot and key, including after auth recovery', async () => {
  const submit = createArchiveRequests(), calls: { ids: string[]; key: string }[] = []
  const send = async (_: string, ids: string[], key: string) => {
    calls.push({ ids, key })
    if (calls.length === 1) throw new Error('lost response')
    if (calls.length === 2) throw Object.assign(new Error('expired'), { status: 401 })
    return result
  }
  await assert.rejects(submit('u', 't', ['v1'], send))
  await assert.rejects(submit('u', 't', ['v2'], send))
  assert.equal(await submit('u', 't', ['v2'], send), result)
  assert.deepEqual(calls[0], calls[1]); assert.deepEqual(calls[0], calls[2])
  await submit('u', 't', ['v2'], send)
  assert.deepEqual(calls[3].ids, ['v2']); assert.notEqual(calls[3].key, calls[0].key)
})
test('identity changes isolate snapshots and definitive rejection permits fresh action', async () => {
  const submit = createArchiveRequests()
  await assert.rejects(submit('u', 't', ['v1'], async () => { throw new Error('network') }))
  await submit('other', 't', ['v2'], async (_, ids) => { assert.deepEqual(ids, ['v2']); return result })
  await assert.rejects(submit('u', 't', ['v2'], async (_, ids) => {
    assert.deepEqual(ids, ['v1']); throw Object.assign(new Error('changed'), { status: 409 })
  }))
  await submit('u', 't', ['v2'], async (_, ids) => { assert.deepEqual(ids, ['v2']); return result })
})
