import { identity, checkIdentityResponse } from './identity'

/** 将响应体消费也纳入读取生命周期，避免仅响应头到达后就释放取消控制。 */
export async function readIdentityBlob(url: string, init: RequestInit = {}, fetcher: typeof fetch = fetch) {
  const reading = identity.read()
  let responseEpoch = reading.epoch
  try {
    const response = await fetcher(url, {
      credentials: 'include', ...init,
      signal: init.signal ? AbortSignal.any([reading.signal, init.signal]) : reading.signal
    })
    reading.assert()
    responseEpoch = await checkIdentityResponse(response.status, reading.epoch)
    identity.assert(responseEpoch)
    if (!response.ok) {
      let message = `下载请求失败（${response.status}）`
      try {
        const value: unknown = await response.json()
        if (value && typeof value === 'object' && 'message' in value && typeof value.message === 'string') message = value.message
      } catch { /* 非 JSON 网关错误保留状态提示 */ }
      identity.assert(responseEpoch)
      throw new Error(message)
    }
    const blob = await response.blob()
    reading.assert()
    return blob
  } catch (error) {
    identity.assert(responseEpoch)
    throw error
  } finally { reading.release() }
}
