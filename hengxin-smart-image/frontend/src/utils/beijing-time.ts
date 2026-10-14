/** Business timestamps are always displayed in Beijing, independent of browser timezone. */
const formatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
})

export function formatBeijingTime(value: string | Date | null | undefined, fallback = '—'): string {
  if (!value) return fallback
  let input: string | Date = value
  if (typeof input === 'string') {
    input = input.trim()
    // Legacy preview/display values are Beijing wall-clock times, not UTC timestamps.
    const local = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})[ T](\d{1,2}):(\d{2})(?::(\d{2})(\.\d+)?)?$/.exec(input)
    if (local) {
      const [, y, m, d, h, minute, second = '00', fraction = ''] = local
      input = `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}T${h.padStart(2, '0')}:${minute}:${second}${fraction}+08:00`
    } else if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$/i.test(input)) return fallback
  }
  if (typeof input === 'string') {
    const fields = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(input)
    if (!fields) return fallback
    const [, year, month, day, hour, minute, second] = fields.map(Number)
    if (year < 1 || month < 1 || month > 12 || day < 1
      || day > new Date(Date.UTC(year, month, 0)).getUTCDate()
      || hour > 23 || minute > 59 || second > 59) return fallback
  }
  const date = input instanceof Date ? input : new Date(input)
  if (!Number.isFinite(date.getTime())) return fallback
  const parts = Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value]))
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
}

/** Element Plus value-format supplies a wall-clock string; attach the business timezone. */
export function beijingFilterTime(value: string | null | undefined): string {
  return value ? `${value.replace(' ', 'T')}+08:00` : ''
}
