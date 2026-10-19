import { test } from 'node:test'
import assert from 'node:assert/strict'
import { archivePictureUrl, isArchive, isArchiveDetail, type ArchiveDetail, type ArchiveEvent } from '../src/api/overseas/archives'
import { formatBeijingTime } from '../src/utils/beijing-time'
const event: ArchiveEvent = { id: 'event', actorId: 'actual', actorName: '实际归档人', at: '2026-10-19T01:02:03+00:00', pictures: [{ id: 'picture', name: '产品图.png', sku: 'SKU-A' }] }
const archive: ArchiveDetail = { id: 'archive', taskId: null, sourceDeleted: true, productName: '产品', brand: '品牌', platform: 'Amazon', skus: [{ code: 'SKU-A' }], pictureCount: 1, createdAt: '2026-10-19T00:00:00Z', latestArchive: event, archiveHistory: [event], historyIncomplete: false, pictures: [{ id: 'picture', name: '产品图.png', sku: 'SKU-A', width: 10, height: 10, contentType: 'image/png', sizeBytes: 10, url: archivePictureUrl('archive', 'picture') }] }

test('归档审计兼容旧接口，真实时间以北京时间显示', () => {
  assert.ok(isArchiveDetail(archive, archive.id))
  assert.equal(formatBeijingTime(event.at), '2026-10-19 09:02:03')
  const { latestArchive, archiveHistory, historyIncomplete, ...legacy } = archive
  assert.ok(isArchiveDetail(legacy, legacy.id))
  assert.ok(isArchiveDetail({ ...archive, latestArchive: null, archiveHistory: [], historyIncomplete: true }, archive.id))
})

test('新增可选审计字段存在时必须有效，不接受静默丢弃或跨归档图片', () => {
  for (const value of [false, {}, { ...event, actorName: 42 }, { ...event, actorId: '' }, { ...event, at: 'not-a-date' }, { ...event, at: '2026-10-19T01:02:03' }, { ...event, pictures: [] }, { ...event, pictures: [{ id: 'p', name: 'p', sku: null }] }]) {
    assert.equal(isArchive({ ...archive, latestArchive: value }), false)
  }
  for (const change of [
    { historyIncomplete: null }, { archiveHistory: null }, { archiveHistory: [event, event] },
    { archiveHistory: [{ ...event, pictures: [{ id: 'foreign', name: '产品图.png', sku: 'SKU-A' }] }] },
    { archiveHistory: [{ ...event, pictures: [{ id: 'picture', name: '产品图.png', sku: 'SKU-B' }] }] },
    { archiveHistory: [] }, { latestArchive: null },
  ]) assert.equal(isArchiveDetail({ ...archive, ...change }, archive.id), false)
})
