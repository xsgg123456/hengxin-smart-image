import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { authError, type Account, type Authorization, type CodexAuthApi, type Intent } from '../../api/codex-auth'
import { record } from '../../api/identity/request'

export function useAuthorization(api: CodexAuthApi, intent: Intent, revision: number,
  events: { close: () => void; activate: (account: Account, different: boolean) => void; failure: (reason: unknown) => void }) {
  const authorization = ref<Authorization>(), busy = ref(false), polling = ref(false), error = ref(''), acknowledged = ref(false)
  const clock = ref(Date.now())
  const remaining = computed(() => Math.max(0, Math.ceil((authorization.value?.expiresAt || 0) - clock.value / 1000)))
  const step = computed(() => authorization.value?.step || 'starting')
  let active = true, settled = false, epoch = 0
  let timer: ReturnType<typeof setTimeout> | undefined, ticker: ReturnType<typeof setInterval> | undefined
  const clear = () => { epoch++; clearTimeout(timer) }
  const report = (reason: unknown) => { if (active) { error.value = authError(reason); events.failure(reason) } }
  function schedule() {
    clearTimeout(timer)
    if (active && ['starting', 'waiting', 'checking'].includes(step.value)) timer = setTimeout(() => void poll(), 1500)
  }
  async function poll() {
    if (!active || busy.value || polling.value || !authorization.value) return
    polling.value = true; error.value = ''; const current = epoch
    try {
      const result = await api.poll(authorization.value.id)
      if (active && current === epoch) { authorization.value = result; schedule() }
    } catch (reason) { if (current === epoch) report(reason) }
    finally { if (active) polling.value = false }
  }
  async function start() {
    if (!active || busy.value) return
    clear(); busy.value = true; error.value = ''; acknowledged.value = false
    try {
      if (authorization.value) { await cancelExisting(authorization.value.id); authorization.value = undefined }
      if (!active) return
      const result = await startAfterCleanup()
      if (!result) return
      if (!active) { void api.cancel(result.id).catch(() => {}); return }
      authorization.value = result; schedule()
    } catch (reason) { report(reason) }
    finally { if (active) busy.value = false }
  }
  async function cancelExisting(id: string) {
    try { await api.cancel(id) }
    catch (reason) { if (!record(reason) || reason.status !== 404) throw reason }
  }
  async function startAfterCleanup(): Promise<Authorization | undefined> {
    for (let attempt = 0; active; attempt++) {
      try { return await api.start(intent, revision) }
      catch (reason) {
        const message = record(reason) ? String(reason.detail || reason.message || '') : ''
        if (!record(reason) || reason.status !== 409 || !/正在结束|正在清理|流程.*结束|仍在退出/.test(message) || attempt >= 5) throw reason
        await new Promise(resolve => setTimeout(resolve, 800))
      }
    }
  }
  async function retry() {
    if (!authorization.value || busy.value) return
    clear(); busy.value = true; error.value = ''
    try { const result = await api.retry(authorization.value.id); if (active) { authorization.value = result; schedule() } }
    catch (reason) { report(reason) }
    finally { if (active) busy.value = false }
  }
  async function activate() {
    if (!authorization.value || step.value !== 'verified' || busy.value || (authorization.value.different && !acknowledged.value)) return
    clear(); busy.value = true; error.value = ''
    try {
      const result = await api.activate(authorization.value.id, acknowledged.value)
      settled = true
      if (active) events.activate(result, authorization.value.different)
    } catch (reason) { report(reason) }
    finally { if (active) busy.value = false }
  }
  async function close() {
    if (busy.value) return
    clear(); busy.value = true; error.value = ''
    try {
      if (authorization.value && !settled) await cancelExisting(authorization.value.id)
      settled = true
      if (active) events.close()
    } catch (reason) { report(reason) }
    finally { if (active) busy.value = false }
  }
  onMounted(() => { ticker = setInterval(() => { clock.value = Date.now() }, 1000); void start() })
  onBeforeUnmount(() => {
    active = false; clear(); clearInterval(ticker)
    if (authorization.value && !settled) void api.cancel(authorization.value.id).catch(() => {})
  })
  return { authorization, step, remaining, busy, polling, error, acknowledged, start, poll, retry, activate, close }
}
