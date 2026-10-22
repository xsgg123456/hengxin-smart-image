import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent } from 'vue'
import { mount, flush } from './membership-test-harness'
import { useStudio } from '../src/views/overseas/studio/use-studio'
import { handleStudioSendKey } from '../src/views/overseas/studio/studio-send-key'
import { emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import type { Studio, StudioApi, TurnInput } from '../src/api/overseas/studio'
import { IdentityError } from '../src/api/identity/request'

const task: TaskDetail = { ...emptyTaskDraft(), id: 'keyboard-task', status: 'studio', workflow: 'studio', version: 1, createdAt: '', updatedAt: '', createdBy: { id: 'u', name: '用户' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: ['task.design'], events: [] }
const snapshot = (): Studio => ({ taskId: task.id, taskVersion: 1, archiveId: null, reopened: false, completed: false, turns: [], materials: [], skills: [{ id: "skill-id", name: "test", displayName: "测试 Skill", description: "" }], activeTurnId: null })
const enter = () => ({ key: 'Enter', keyCode: 13, preventDefault() {} }) as KeyboardEvent

test('键盘进入正式send，保持附件Skill原文；上传/进行中/pending/无权限/空输入门禁一致', async () => {
  let state!: ReturnType<typeof useStudio>
  let currentTask = task
  let failed = false
  const sent: TurnInput[] = []
  const api: StudioApi = {
    get: async () => snapshot(), transcript: async () => ({ items: [], cursor: 0, hasMore: false }),
    events: async () => ({ items: [], cursor: 0 }), newConversation: async () => snapshot(),
    cancel: async () => snapshot(), archive: async () => snapshot(), complete: async () => snapshot(), reopen: async () => snapshot(),
    removeMaterial: async () => snapshot(), upload: async () => { throw Error('本测试不上传') },
    send: async (_id, body) => { sent.push(body); if (failed) throw new IdentityError(0, '网络中断'); return snapshot() }
  }
  const view = mount(defineComponent({ setup() { state = useStudio(() => currentTask, () => {}, () => {}, api); return () => null } }))
  try {
    await flush()
    handleStudioSendKey(enter(), state.send)
    assert.equal(sent.length, 0, '空输入不发')
    state.text.value = ' 保留原文\n'; state.skill.value = 'skill-id'
    state.attachments.value = [{ id: 'upload:file', name: '说明.pdf', source: 'upload', contentType: 'application/pdf', sizeBytes: 10, url: '/file' }]
    state.uploading.value = true
    handleStudioSendKey(enter(), state.send); assert.equal(sent.length, 0)
    state.uploading.value = false
    state.data.value!.activeTurnId = 'running'
    handleStudioSendKey(enter(), state.send); assert.equal(sent.length, 0)
    state.data.value!.activeTurnId = null
    currentTask = { ...task, capabilities: [] }; state.data.value = { ...state.data.value! }
    handleStudioSendKey(enter(), state.send); assert.equal(sent.length, 0)
    currentTask = task; state.data.value = { ...state.data.value! }
    handleStudioSendKey(enter(), state.send)
    handleStudioSendKey(enter(), state.send)
    assert.equal(sent.length, 1, '鼠标共用send的busy防重仍有效')
    await flush()
    assert.deepEqual(sent[0], { text: ' 保留原文\n', skillId: 'skill-id', attachmentIds: ['upload:file'], referencePictureIds: [] })
    state.text.value = '结果未知'; failed = true
    handleStudioSendKey(enter(), state.send); await flush()
    assert.ok(state.pending.value)
    handleStudioSendKey(enter(), state.send); await flush()
    assert.equal(sent.length, 2, 'pending时不能创建新发送')
  } finally { view.close() }
})
