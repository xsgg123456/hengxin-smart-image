import { IdentityError, type Member, type Identity } from './auth'

interface Dependencies {
  identity: () => Promise<Identity>
  member: () => Promise<Member>
  accept: (member: Member, name: string) => void
  reject: (reason: unknown) => void
  pending: (value: boolean) => void
}

// Recheck the existing session without exchanging tickets or discarding the page.
export function createOverseasRevalidator(deps: Dependencies) {
  let generation = 0
  let running: Promise<void> | undefined
  function invalidate() {
    ++generation
    running = undefined
    deps.pending(false)
  }
  function run(): Promise<void> {
    if (running) return running
    const epoch = ++generation
    deps.pending(true)
    running = (async () => {
      try {
        const identity = await deps.identity()
        if (epoch !== generation) return
        const member = await deps.member()
        if (!identity.sessionId || member.identitySessionId !== identity.sessionId) throw new IdentityError(401, '企业身份已变化，请重新选择业务')
        if (epoch !== generation) return
        const latest = await deps.identity()
        if (latest.sessionId !== identity.sessionId) throw new IdentityError(401, '企业身份已变化，请重新选择业务')
        if (epoch === generation) deps.accept(member, identity.name)
      } catch (reason) {
        if (epoch === generation) deps.reject(reason)
      } finally {
        if (epoch === generation) { running = undefined; deps.pending(false) }
      }
    })()
    return running
  }
  return { run, invalidate }
}
