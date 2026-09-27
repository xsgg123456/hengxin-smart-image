/** 会话代次独立于业务版本；仅取消读取，不取消已经提交的写操作。 */
export class StaleIdentityError extends Error {
  readonly code = 'STALE_IDENTITY'
  readonly status = 0
  constructor() { super('身份已变化，请重新确认操作结果') }
}
type Reason = 'changed' | 'invalid' | 'suspended'
export function createIdentity() {
  let epoch = 0
  let probe: (() => Promise<unknown>) | undefined
  let probing: { epoch: number; promise: Promise<void> } | undefined
  let lastProbe = -Infinity
  const reads = new Set<AbortController>()
  const listeners = new Set<(reason: Reason) => void>()
  const current = (value: number) => value === epoch
  const assert = (value: number) => { if (!current(value)) throw new StaleIdentityError() }
  function advance(reason: Reason) {
    epoch++
    lastProbe = -Infinity
    reads.forEach(controller => controller.abort())
    reads.clear()
    listeners.forEach(listener => listener(reason))
  }
  function invalidate(value: number) { if (current(value)) advance('invalid') }
  async function verify(value: number, limited = false): Promise<void> {
    if (!current(value) || !probe) return
    if (probing?.epoch === value) return probing.promise
    if (limited && Date.now() - lastProbe < 3000) return
    lastProbe = Date.now()
    const promise = Promise.resolve().then(probe).then(() => {}, error => {
      if (error && typeof error === 'object' && 'status' in error && (error.status === 401 || error.status === 403)) invalidate(value)
    }).finally(() => { if (probing?.promise === promise) probing = undefined })
    probing = { epoch: value, promise }
    return promise
  }
  return {
    get epoch() { return epoch }, current, assert, advance, invalidate, verify,
    configureProbe(callback: () => Promise<unknown>) { probe = callback },
    subscribe(callback: (reason: Reason) => void) { listeners.add(callback); return () => { listeners.delete(callback) } },
    read() {
      const value = epoch, controller = new AbortController()
      reads.add(controller)
      return { epoch: value, signal: controller.signal, assert: () => assert(value), release: () => { reads.delete(controller) } }
    }
  }
}
export const identity = createIdentity()

export async function checkIdentityResponse(status: number, epoch: number, auth = false) {
  identity.assert(epoch)
  if (status === 401 || (auth && status === 403)) {
    identity.invalidate(epoch)
    return epoch + 1
  }
  if (status === 403) await identity.verify(epoch)
  identity.assert(epoch)
  return epoch
}
