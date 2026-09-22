import type { TaskDetailData } from '../../types/hengxin'

/** 只统计当前轮次目标，保留的旧版本不是本轮产出。 */
export function taskOutcome(data: TaskDetailData) {
  const round = data.rounds.find(item => item.id === data.task.currentRoundId)
  if (!round) return undefined
  const slots = data.slots.filter(slot => round.target === null || slot.slot === round.target)
  const succeeded = slots.filter(slot => !slot.error && slot.versions.some(version => version.roundId === round.id)).length
  const failed = slots.filter(slot => !!slot.error).length
  const unfinished = slots.length - succeeded - failed
  const target = round.target === null ? `整套 ${slots.length} 张` : `第 ${round.target + 1} 张`
  return { total: slots.length, succeeded, failed, unfinished, target,
    summary: `本轮 ${slots.length} 张 · 成功 ${succeeded} 张 · 失败 ${failed} 张${unfinished ? ` · 未完成 ${unfinished} 张` : ''}`,
    retry: `重试范围：${target}，沿用本轮意见。已有结果保留，重试成功后更新对应位置。` }
}
