import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildImageEditPrompt, IMAGE_EDIT_TEMPLATE } from '../src/views/hengxin/api-image-edits/image-edit-prompt'
import { buildTextEditPrompt, TEXT_EDIT_TEMPLATE } from '../src/views/hengxin/api-image-edits/text-edit-prompt'
import { createItemCommand, type ItemCommand } from '../src/views/hengxin/api-image-edits/item-command'
import { createApiImageClient } from '../src/api/api-image-edits'
import { operationLabel } from '../src/types/api-image-edits'

test('图片模板与后端一致，通用规则和文字规则互斥，用户输入原样拼接', () => {
  assert.equal(IMAGE_EDIT_TEMPLATE, readFileSync(new URL('../../backend/app/modules/api_image_edits/image_edit_prompt.txt', import.meta.url), 'utf8').replace(/\r\n/g, '\n'))
  assert.doesNotMatch(IMAGE_EDIT_TEMPLATE, /手机|摄像头|壁纸|顶部居中/)
  assert.match(IMAGE_EDIT_TEMPLATE, /不修改任何文字内容/)
  assert.match(TEXT_EDIT_TEMPLATE, /分两次/)
  for (const text of ['移除右侧多余物体', '将标注区域改为蓝色', '缩小标注物体，其他不变', '位置调整 $& $$ $`']) {
    assert.equal(buildImageEditPrompt(text), IMAGE_EDIT_TEMPLATE.replace('{{用户本次填写的修改意见及各处标注说明}}', () => text))
    assert.notEqual(buildImageEditPrompt(text), buildTextEditPrompt(text))
  }
  assert.equal(operationLabel('image_edit'), '图片修改')
})

test('图片未知请求确认始终复用原类型/提示词/标注，不能被文字请求替换', async () => {
  const calls: { input: unknown; key: string | null }[] = []
  let unavailable = true
  const api = createApiImageClient('/api/v1', async (_url, init) => {
    calls.push({ input: JSON.parse(String(init?.body)), key: new Headers(init?.headers).get('Idempotency-Key') })
    if (unavailable) throw new Error('响应丢失')
    return new Response(JSON.stringify({ taskId: 't' }), { headers: { 'content-type': 'application/json' } })
  })
  const state = createItemCommand(undefined, () => 'image-key')
  const image: ItemCommand = { kind: 'revise', input: { kind: 'image_edit', baseVersion: 2, text: '缩小物体', prompt: buildImageEditPrompt('缩小物体'), annotationFileId: 'image-mark' } }
  const send = (command: ItemCommand, key: string) => {
    if (command.kind !== 'revise') throw new Error('unexpected command')
    return api.revise('t', 'i', command.input, key)
  }
  assert.equal(await state.submit(image, send), false)
  image.input.text = '后来输入不影响冻结请求'
  unavailable = false
  assert.equal(await state.submit({ kind: 'revise', input: { kind: 'text_edit', baseVersion: 3, text: '改字', annotationFileId: 'text-mark' } }, send), true)
  assert.deepEqual(calls[1], calls[0])
  assert.equal((calls[1].input as { kind: string }).kind, 'image_edit')
})
