import test from 'node:test'
import assert from 'node:assert/strict'
import { createDomesticArchivesApi } from '../src/api/hengxin/domestic-archives'
import { IdentityError } from '../src/api/identity/request'
import { archiveTranscript } from '../src/views/hengxin/domestic-studio/archive-transcript'

const archive = '10000000-0000-4000-8000-000000000001'
const picture = '20000000-0000-4000-8000-000000000001'
const annotation = '30000000-0000-4000-8000-000000000001'
const reference = '30000000-0000-4000-8000-000000000002'
const other = '40000000-0000-4000-8000-000000000001'
const file = (id: string, kind: 'picture' | 'upload') => ({ id, kind, name: '图片.png',
  contentType: 'image/png', sizeBytes: 12, width: kind === 'picture' ? 8 : null, height: kind === 'picture' ? 6 : null,
  url: `/api/v1/domestic-studio/archives/${archive}/files/${id}/content` })
const fixture = () => ({ id: archive, productName: '产品', workspace: 'camera', conversationName: '会话',
  createdAt: '2026-11-12T00:00:00Z', pictureCount: 1, cover: file(picture, 'picture'), deletionStatus: null,
  deletionError: null, turns: [{ id: other, text: '修改要求', actorName: '张三', createdAt: '2026-11-12T00:00:00Z',
    reply: '完成', replyAt: null, status: 'succeeded', error: null,
    transcript: [{ itemId: 'event-1', kind: 'message', text: '公开进度', state: 'completed', createdAt: '2026-11-12T00:00:00Z' }],
    pictures: [file(picture, 'picture')], outputs: [],
    referencePictures: [file(picture, 'picture')], attachments: [file(annotation, 'upload'), file(reference, 'upload')],
    imageEdits: [{ pictureId: picture, annotationId: `upload:${annotation}`, text: '修改一处',
      references: [{ attachmentId: `upload:${reference}`, kind: 'custom', customPurpose: '背景材质', note: '参考纹理' }] }] }] })

test('归档详情接受逐图对应的修改资料及没有修改资料的旧归档', async () => {
  const value = fixture()
  const api = createDomesticArchivesApi(async () => Response.json(value))
  assert.equal((await api.detail(archive)).turns[0].imageEdits?.[0].references?.[0].note, '参考纹理')
  const legacy = fixture()
  delete (legacy.turns[0] as { imageEdits?: unknown }).imageEdits
  delete (legacy.turns[0] as { status?: unknown }).status
  delete (legacy.turns[0] as { error?: unknown }).error
  delete (legacy.turns[0] as { transcript?: unknown }).transcript
  assert.equal((await createDomesticArchivesApi(async () => Response.json(legacy)).detail(archive)).turns[0].imageEdits, undefined)
})

test('归档详情拒绝指向本轮附件或原图以外的修改资料', async () => {
  for (const mutate of [
    (value: ReturnType<typeof fixture>) => { value.turns[0].imageEdits[0].pictureId = other },
    (value: ReturnType<typeof fixture>) => { value.turns[0].imageEdits[0].annotationId = `upload:${other}` },
    (value: ReturnType<typeof fixture>) => { value.turns[0].imageEdits[0].references[0].attachmentId = `upload:${other}` },
    (value: ReturnType<typeof fixture>) => { value.turns[0].attachments[1].url = `/api/v1/domestic-studio/workspaces/camera/files/${reference}/content` },
    (value: ReturnType<typeof fixture>) => { value.turns[0].transcript[0].kind = 'private-reasoning' },
    (value: ReturnType<typeof fixture>) => { value.turns[0].status = 'running' },
  ]) {
    const value = fixture(); mutate(value)
    await assert.rejects(createDomesticArchivesApi(async () => Response.json(value)).detail(archive), IdentityError)
  }
})

test('归档公开过程按归档事件合并，旧资料缺少事件关联时完整保留', () => {
  const entry = { kind: 'message' as const, state: 'completed' as const, createdAt: null }
  const result = archiveTranscript({ id: 'archived-turn', transcript: [
    { ...entry, itemId: 'event-1', text: '旧进度' }, { ...entry, itemId: 'event-2', text: '另一个事件' },
    { ...entry, itemId: 'event-1', text: '最新进度' }, { ...entry, text: '历史未关联一' }, { ...entry, text: '历史未关联二' }
  ] })
  assert.deepEqual(result.map(item => item.text), ['最新进度', '另一个事件', '历史未关联一', '历史未关联二'])
  assert.equal(new Set(result.map(item => item.itemId)).size, 4)
})
