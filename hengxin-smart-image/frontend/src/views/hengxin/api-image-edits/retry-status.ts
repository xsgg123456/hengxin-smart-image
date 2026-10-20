import type { ApiChannel, ApiItem } from '@/types/api-image-edits'

export function remainingSeconds(value: string | null | undefined, now: number) {
  const time = value ? Date.parse(value) : NaN
  return Number.isFinite(time) ? Math.max(0, Math.ceil((time - now) / 1000)) : null
}

export function channelRetryText(channel: ApiChannel | undefined, now: number) {
  if (!channel?.enabled || channel.paused) return ''
  const remaining = remainingSeconds(channel.cooldownUntil, now)
  if (remaining !== null && remaining > 0) return `上游冷却中，至少 ${remaining} 秒后探测恢复；新请求继续排队，已有结果正常保存。`
  if (channel.recovering || channel.cooldownUntil) return '上游恢复探测中，等待发送名额；新请求继续排队，发送速度逐步恢复。'
  return ''
}

export function itemRetryText(item: ApiItem, now: number) {
  if (item.state === 'succeeded') return ''
  if (item.state === 'uncertain') return `${item.retry?.stopRequested ? '已请求停止后续重试；' : ''}请求结果需核实，不会自动重复生成；请联系管理员核实原请求。`
  if (item.retry?.stopRequested) return item.state === 'failed' ? '本轮已停止重试，可手动开启新一轮。' : '已请求停止后续重试；已发出的请求继续收取结果，成功图片仍会保存。'
  if (item.state === 'failed') return ''
  const remaining = remainingSeconds(item.retry?.nextAttemptAt ?? item.nextAttemptAt, now)
  if (remaining !== null) return remaining > 0 ? `距离下次尝试至少 ${remaining} 秒；实际发送由后台安排。` : '等待后台分配发送名额，页面倒计时不会发起请求。'
  return item.state === 'queued' || item.state === 'retry_wait' ? '等待后台分配发送名额。' : ''
}
