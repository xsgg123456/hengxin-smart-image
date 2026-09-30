import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildTextEditPrompt, TEXT_EDIT_TEMPLATE } from '../src/views/hengxin/api-image-edits/text-edit-prompt'
import { DEFAULT_WALLPAPER_PROMPT } from '../src/views/hengxin/api-image-edits/default-wallpaper-prompt'
import { createApiImageClient } from '../src/api/api-image-edits'
import { createItemCommand, type ItemCommand } from '../src/views/hengxin/api-image-edits/item-command'
import { annotationText } from '../src/views/hengxin/components/annotation/annotation-drafts'
import { operationLabel } from '../src/types/api-image-edits'

test('文字修改模板与后端原文相同，逐字嵌入用户意见且不解释替换字符', () => {
  assert.equal(TEXT_EDIT_TEMPLATE, readFileSync(new URL('../../backend/app/modules/api_image_edits/text_edit_prompt.txt', import.meta.url), 'utf8').replace(/\r\n/g, '\n'))
  const text = '标注 1（框选）：将防窥钢化膜改为张帅钢化膜\n保留28° $& $$ $`'
  assert.equal(buildTextEditPrompt(text), TEXT_EDIT_TEMPLATE.split('{{用户输入的修改意见及各处标注说明}}').join(text))
  assert.equal(DEFAULT_WALLPAPER_PROMPT, readFileSync(new URL('../src/views/hengxin/api-image-edits/default-wallpaper-prompt.txt', import.meta.url), 'utf8').replace(/\r\n/g, '\n'))
  assert.ok(DEFAULT_WALLPAPER_PROMPT.length > 1400)
})

test('API文字修改必须有文字意见，纯文字可提交，标注意见保留，CLI图片单独提交兼容', () => {
  const draft = { mode: 'direct' as const, marks: [], general: '只替换指定标题' }
  assert.equal(annotationText(draft, 4000, false), '只替换指定标题')
  const upload = { mode: 'upload' as const, marks: [], general: '', uploaded: new File(['png'], 'mark.png') }
  assert.throws(() => annotationText(upload, 4000, false), /请填写修改意见/)
  assert.equal(annotationText(upload, 4000), '')
  const marked = { ...draft, general: '', marks: [{ id: 'one', kind: 'rect' as const, x: 0, y: 0, width: 30, height: 20, points: [], note: '防窥改为张帅' }] }
  assert.equal(annotationText(marked, 4000, false), '标注 1（框选）：防窥改为张帅')
})

test('真实客户端两类文案载荷和原幂等键明确分离，未知请求不换类型和基础版本', async () => {
  const requests: { input: unknown; key: string | null }[] = []
  let offline = true
  const api = createApiImageClient('/api/v1', async (_url, init) => {
    requests.push({ input: JSON.parse(String(init?.body)), key: new Headers(init?.headers).get('Idempotency-Key') })
    if (offline) throw new Error('响应丢失')
    return new Response(JSON.stringify({ taskId: 't' }), { headers: { 'content-type': 'application/json' } })
  })
  const repair: ItemCommand = { kind: 'revise', input: { kind: 'text_repair', text: '', baseVersion: 3 } }
  const edit: ItemCommand = { kind: 'revise', input: { kind: 'text_edit', text: '标题改为张帅', prompt: buildTextEditPrompt('标题改为张帅'), baseVersion: 4 } }
  const command = createItemCommand(undefined, () => 'original-key')
  const send = (action: ItemCommand, key: string) => { assert.equal(action.kind, 'revise'); if (action.kind !== 'revise') throw new Error(); return api.revise('t', 'i', action.input, key) }
  assert.equal(await command.submit(repair, send), false)
  offline = false
  assert.equal(await command.submit(edit, send), true)
  assert.deepEqual(requests[0], requests[1])
  assert.deepEqual(requests[1].input, repair.input)
  await api.revise('t', 'i', edit.input, 'edit-key')
  await api.revise('t', 'i', { ...edit.input, annotationFileId: 'annotation' }, 'marked-key')
  assert.deepEqual(requests[2].input, edit.input)
  assert.deepEqual(requests[3].input, { ...edit.input, annotationFileId: 'annotation' })
  assert.equal(operationLabel('text_repair'), '修复文案')
  assert.equal(operationLabel('text_edit'), '文字修改')
  assert.equal(operationLabel(), '修改')
})
