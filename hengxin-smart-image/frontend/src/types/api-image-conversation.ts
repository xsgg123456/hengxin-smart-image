import type { ApiPicture } from './api-image-edits'
export type EditTurnStatus = 'queued' | 'running' | 'waiting_user' | 'candidate' | 'adopted' | 'cancelled' | 'failed' | 'uncertain'
export interface EditTurn {
  id: string; status: EditTurnStatus; text: string; prompt: string; baseVersion: number | null; baseTurnId: string | null
  baseFileId: string; annotationFileId: string | null; candidateFileId: string | null; messages: string[]; error: string | null
  createdAt: string; adoptedVersion: number | null; basePicture: ApiPicture | null; candidate: ApiPicture | null; annotation: ApiPicture | null
}
export interface EditRetention { status: 'active' | 'cache_pending' | 'expire_pending' | 'expired'; lastActivityAt: string; expiresAt: string; cacheClearedAt: string | null }
export interface EditConversation { retention?: EditRetention | null; id: string | null; itemId: string; currentVersion: number | null; lastEventId: number; turns: EditTurn[] }
export interface EditTurnInput { restartExpired?: boolean; text: string; prompt: string; baseVersion?: number; baseTurnId?: string; annotationFileId?: string }
export interface EditEvent { id: number; turnId: string; type: 'state' | 'message'; status?: EditTurnStatus; text?: string }
export const editTurnLabels: Record<EditTurnStatus, string> = { queued: '排队中', running: '修改中', waiting_user: '等待补充意见', candidate: '候选图片待确认', adopted: '已采用', cancelled: '已停止', failed: '修改失败', uncertain: '执行结果需核实' }
export const isEditActive = (turn?: EditTurn) => !!turn && ['queued', 'running'].includes(turn.status)
