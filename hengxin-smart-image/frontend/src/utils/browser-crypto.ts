/** HTTP 私网也有 getRandomValues；不向全局注入 polyfill。 */
export function randomUUID(): string {
  const crypto = globalThis.crypto
  if (typeof crypto?.randomUUID === 'function') return crypto.randomUUID()
  if (typeof crypto?.getRandomValues !== 'function') throw new Error('当前浏览器无法提供安全随机数，请使用新版 Chrome 或 Edge')
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export async function sha256(bytes: ArrayBuffer): Promise<string> {
  const subtle = globalThis.crypto?.subtle
  if (typeof subtle?.digest === 'function') {
    const digest = await subtle.digest('SHA-256', bytes)
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
  }
  // WordArray 直接接收原始字节，不能经过 UTF-8 文本转换，否则会破坏二进制摘要。
  const { default: CryptoJS } = await import('crypto-js')
  return CryptoJS.SHA256(CryptoJS.lib.WordArray.create(new Uint8Array(bytes))).toString(CryptoJS.enc.Hex)
}
