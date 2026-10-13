/** Rendering data only: never interprets formulas, markup or links from uploads. */
export interface TextSheet { name: string; rows: string[][] }
export function materialSheets(text: string): TextSheet[] {
  const result: TextSheet[] = []
  for (const line of text.split('\n')) {
    const match = /^\[([^\]]+)\] (.*)$/.exec(line)
    const name = match?.[1] || '资料内容', value = match?.[2] ?? line
    let sheet = result.find(item => item.name === name)
    if (!sheet) { sheet = { name, rows: [] }; result.push(sheet) }
    sheet.rows.push(value.split('\t'))
  }
  return result
}
export function materialTextPages(text: string, size = 8000): string[] {
  const chars = Array.from(text), pages: string[] = []
  for (let i = 0; i < chars.length; i += size) pages.push(chars.slice(i, i + size).join(''))
  return pages.length ? pages : ['本版本未解析出可读内容']
}
