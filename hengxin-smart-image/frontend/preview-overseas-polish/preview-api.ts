import type { StudioApi, Studio } from '@/api/overseas/studio'
import type { TaskDetail } from '@/api/overseas/tasks'
export { sampleText } from './sample'
const now = '2026-10-24T08:00:00Z'
export const task: TaskDetail = {
  id: 'polish-preview', name: '直杆实木布罩灯 · 主图设计', productName: '直杆实木布罩灯', brand: 'OUTON', platform: 'Amazon', market: '美国站', remarks: '', skus: [{ code: 'H-ZGD0008' }], status: 'studio', workflow: 'studio', version: 1,
  createdAt: now, updatedAt: now, createdBy: { id: 'preview-operator', name: '运营' }, designer: { id: 'preview-designer', name: '张帅', status: 'active', eligible: true }, capabilities: ['task.design'], events: [],
}
const names = ['overview','temperature','dimming','control','timer','memory','wood','dimensions','assembly','living','bedroom','study','reading','dining']
const imageUrl = new URL('../preview-ai-studio/assets/sample-1.jpg', import.meta.url).href
const documentUrl = new URL('../preview-ai-studio/assets/task-brief.txt', import.meta.url).href
function snapshot(conversationId = 'preview-session-1'): Studio {
  return {
    taskId: task.id, taskVersion: 1, archiveId: null, reopened: false, completed: false, activeTurnId: null, conversationId,
    conversations: [1, 2].map(i => ({ id: `preview-session-${i}`, name: `会话 ${i}`, version: 1, createdAt: now, updatedAt: now, activeTurnId: null, status: 'succeeded', turnCount: 1 })), activeConversationCount: 0, maxConversations: 10,
    turns: [{ id: `turn-${conversationId}`, text: '请结合产品资料制作整套图片。', skillName: null, status: 'succeeded', reply: '本轮图片已完成，可选择归档或继续提出修改意见。', error: null, jobId: 'preview-job', jobVersion: 1, attachments: [], referencePictures: [], createdAt: now, conversationId,
      pictures: names.map((name, i) => ({ id: `${conversationId}-picture-${i}`, name: `${String(i + 1).padStart(2, '0')}_${name}.jpg`, url: imageUrl, width: 800, height: 800, turnId: `turn-${conversationId}`, sku: null, archived: false })) }],
    materials: Array.from({ length: 18 }, (_, i) => ({ id: `task:preview-${i}`, name: i === 0 ? '产品说明（示例）.txt' : `${19-i}.jpg`, contentType: i === 0 ? 'text/plain' : 'image/jpeg', sizeBytes: 420100, url: i === 0 ? documentUrl : imageUrl, source: 'task' as const })), skills: [],
  }
}
async function unsupported(): Promise<never> { throw Error('当前仅预览界面，不执行上传、生成或任务操作。') }
export const previewApi: StudioApi = {
  get: async (_id, _signal, conversationId) => snapshot(conversationId),
  transcript: async () => ({ items: [], cursor: 0, hasMore: false }), events: async () => ({ items: [], cursor: 0 }),
  send: unsupported, cancel: unsupported, archive: unsupported, complete: unsupported, reopen: unsupported, upload: unsupported,
  newConversation: unsupported, renameConversation: unsupported, deleteConversation: unsupported, removeMaterial: unsupported,
}
