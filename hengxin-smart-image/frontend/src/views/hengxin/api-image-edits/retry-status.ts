import { itemLabels, type ApiChannel, type ApiItem, type ApiTask } from '@/types/api-image-edits'

export function channelRetryText(channel?: ApiChannel) {
  if (!channel?.enabled || channel.paused) return ''
  return channel.recovering || channel.cooldownUntil ? '服务繁忙，正在等待处理，请稍候。' : ''
}

export function itemStatusText(item: ApiItem) {
  return item.state === 'failed' && item.retry?.stopRequested ? '已停止' : itemLabels[item.state]
}

export function taskProgressText(task: ApiTask, channel?: ApiChannel) {
  const success = task.items.filter(item => item.state === 'succeeded').length
  const failed = task.items.filter(item => item.state === 'failed').length
  const active = task.items.filter(item => !['succeeded', 'failed'].includes(item.state))
  const progress = `已完成 ${success}/${task.items.length} 张`
  if (task.status === 'succeeded') return `${progress}，可以下载图片。`
  if (channel && (!channel.enabled || channel.paused)) return `${progress}，服务暂不可用，请稍后再试。`
  if (active.length) {
    if (failed) return `${progress}，${failed} 张未完成可逐张重试，其余正在处理。`
    if (active.every(item => item.state === 'collecting')) return `${progress}，其余正在保存。`
    if (channelRetryText(channel)) return `${progress}，服务繁忙，请稍候。`
    if (active.every(item => item.state === 'queued')) return `${progress}，正在等待处理。`
    if (active.some(item => ['running', 'uncertain'].includes(item.state))) return `${progress}，其余正在生成。`
    if (active.some(item => item.state === 'retry_wait')) return `${progress}，其余正在自动重试。`
    return `${progress}，其余正在处理。`
  }
  if (failed && task.items.filter(item => item.state === 'failed').every(item => item.retry?.stopRequested)) return `${progress}，已停止自动重试，可点击重试继续。`
  return `${progress}，${failed} 张未完成，可点击重试。`
}
