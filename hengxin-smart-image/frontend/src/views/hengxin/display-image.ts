// Display requests remain same-origin and authorized. Preview/download keep originals.
export function displayImageUrl(url: string, size: 256 | 1024 = 256): string {
  if (!/^\/api\/v1\/(?:api-image-edits\/)?files\/[0-9a-f-]+\/content(?:\?|$)/i.test(url)) return url
  const [path, query = ''] = url.split('?')
  const params = new URLSearchParams(query)
  if (params.has('download')) return url
  params.set('variant', String(size))
  return `${path}?${params}`
}
