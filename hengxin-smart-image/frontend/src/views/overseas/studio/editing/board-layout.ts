/** Keep the approved six-picture layout while fitting any group into the same viewport. */
export function boardLayout(count: number) {
  const columns = Math.max(1, Math.ceil(Math.sqrt(count * 1.5)))
  const rows = Math.max(1, Math.ceil(count / columns))
  return { columns, fitZoom: Math.min(1, 1236 / (columns * 408 + 12), 720 / (rows * 356 + 8)) }
}
