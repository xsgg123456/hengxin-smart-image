import { onBeforeUnmount, onMounted, ref } from 'vue'
import { authError, type Account, type CodexAuthApi } from '../../api/codex-auth'

export function useAccount(api: CodexAuthApi, failure: (reason: unknown) => void) {
  const account = ref<Account>(), loading = ref(false), busy = ref(false), error = ref(''), notice = ref('')
  let active = true, timer: ReturnType<typeof setTimeout> | undefined
  function schedule() {
    clearTimeout(timer)
    if (active && account.value?.checking) timer = setTimeout(() => void load(), 1500)
  }
  function report(reason: unknown) { if (active) { error.value = authError(reason); failure(reason) } }
  async function load() {
    if (!active || loading.value || busy.value) return
    loading.value = true; error.value = ''; clearTimeout(timer)
    try { const result = await api.get(); if (active) { account.value = result; schedule() } }
    catch (reason) { report(reason) }
    finally { if (active) loading.value = false }
  }
  async function mutate(action: () => Promise<Account>, message = '') {
    if (!active || busy.value || loading.value) return false
    busy.value = true; error.value = ''; notice.value = ''; clearTimeout(timer)
    try {
      const result = await action()
      if (!active) return false
      account.value = result; notice.value = message; schedule(); return true
    } catch (reason) { report(reason); return false }
    finally { if (active) busy.value = false }
  }
  function enabled(result: Account, different: boolean) {
    if (!active) return
    account.value = result; error.value = ''
    notice.value = different ? '新账号已启用。后续新任务使用新账号，旧会话续接需单独确认。' : '授权已启用。失败操作请返回任务重新发送。'
    schedule()
  }
  onMounted(load)
  onBeforeUnmount(() => { active = false; clearTimeout(timer) })
  return { account, loading, busy, error, notice, load, mutate, enabled }
}
