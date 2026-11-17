import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
export { domesticWorkspaces }
export const labels: Record<string, string> = { empty: '未开始', queued: '排队中', running: '执行中', succeeded: '已回复', failed: '执行失败', cancelled: '已停止', collecting: '收取结果中', cancelling: '正在停止', uncertain: '执行状态待核实', partial: '部分完成', unknown: '状态待核实' }
export const statusOptions = ['', 'running', 'queued', 'succeeded', 'failed', 'empty', 'cancelled', 'unknown']
export const workspaceName = (key: string) => domesticWorkspaces.find(item => item.key === key)?.title || key
export const tagType = (status: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' => status === 'running' ? 'primary' : status === 'succeeded' ? 'success' : status === 'failed' ? 'danger' : status === 'queued' ? 'warning' : 'info'
