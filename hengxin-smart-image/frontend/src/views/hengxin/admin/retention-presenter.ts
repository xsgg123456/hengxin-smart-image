import type { RetentionResult } from '../../../types/retention'
export const resultLabels: Record<RetentionResult, string> = {
  cache_cleared: '缓存已清理', complete: '全部完成', objects_pending: '文件回收中', retry: '失败待重试',
  protected: '暂缓清理', waiting: '等待到期', due: '已到期待处理', processing: '正在清理'
}
export const kindLabels = { cache: '缓存', history: '会话历史' }
export const tagType = (result: RetentionResult) => result === 'complete' || result === 'cache_cleared' ? 'success' : result === 'retry' ? 'danger' : result === 'waiting' ? 'info' : 'warning'
export const count = (value: number | null | undefined) => value == null ? '未知' : value
