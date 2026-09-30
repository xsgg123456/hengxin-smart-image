import { test } from 'node:test'
import assert from 'node:assert/strict'
import { revisionReferences } from '../src/views/hengxin/api-image-edits/revision-references'
import { createItemCommand, type ItemCommand, type PendingCommand } from '../src/views/hengxin/api-image-edits/item-command'

const picture = (id: string) => ({ fileId: id, name: `${id}.png`, url: `/images/${id}` })
test('图片三参考输入按当前选定版本、原图、共用素材排序；文字仅当前成品', () => {
  const current = picture('restored-v1'), source = picture('original'), material = picture('material')
  const refs = revisionReferences('image_edit', current, source, material)
  assert.deepEqual(refs.map(r => r.picture.fileId), ['restored-v1', 'original', 'material'])
  current.fileId = 'later-v4'
  assert.equal(refs[0].picture.fileId, 'restored-v1')
  assert.equal(revisionReferences('text_edit', current, null, null).length, 1)
  assert.throws(() => revisionReferences('image_edit', current, null, material), /对应原图不可用/)
  assert.throws(() => revisionReferences('image_edit', current, source, null), /共用素材不可用/)
  assert.throws(() => revisionReferences('image_edit', null, source, material), /当前成品不可用/)
})

test('旧未知请求恢复保持原载荷和提示词，不补造新参考图片', async () => {
  const original: PendingCommand = { key: 'old-v1', uncertain: true, command: { kind: 'revise', input: { kind: 'image_edit', baseVersion: 1, text: '旧意见', prompt: '旧v1规则', annotationFileId: 'old-mark' } } }
  const operation = createItemCommand({ load: () => original, save: () => {} })
  const next: ItemCommand = { kind: 'revise', input: { kind: 'image_edit', baseVersion: 2, text: '新意见' }, references: revisionReferences('image_edit', picture('v2'), picture('source'), picture('material')) }
  await operation.submit(next, async (command, key) => {
    assert.equal(key, 'old-v1'); assert.deepEqual(command, original.command)
    assert.equal(command.kind === 'revise' && command.references, undefined)
  })
})

test('新未知请求保存预览参考元数据，后续页面数据改变不能改写冻结记录', async () => {
  const refs = revisionReferences('image_edit', picture('v2'), picture('source'), picture('material'))
  const command: ItemCommand = { kind: 'revise', input: { kind: 'image_edit', baseVersion: 2, text: '意见', prompt: '冻结提示词' }, references: refs }
  const operation = createItemCommand(undefined, () => 'new-v2')
  await operation.submit(command, async () => { throw new Error('断网') })
  refs[0].picture.fileId = 'changed'
  const pending = operation.state.pending?.command
  assert.equal(pending?.kind === 'revise' && pending.references?.[0].picture.fileId, 'v2')
})
