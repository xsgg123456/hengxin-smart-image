import { formatBeijingTime } from '@/utils/beijing-time'
export type RecordsPeriod = 'all' | 'today' | 'week' | 'month' | 'custom'
export function recordsDateRange(period: RecordsPeriod, dates: [string, string] | null, now = new Date()) {
  if (period === 'all') return {}
  if (period === 'custom') return dates?.[0] && dates?.[1] ? { dateFrom: dates[0], dateTo: dates[1] } : {}
  const today = formatBeijingTime(now).slice(0, 10)
  const start = new Date(`${today}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() - (period === 'week' ? 6 : period === 'month' ? 29 : 0))
  return { dateFrom: start.toISOString().slice(0, 10), dateTo: today }
}
