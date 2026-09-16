import { ref, watch, type Ref } from 'vue'
import { ApiError } from '../../../api/hengxin/http'
import type { ManagedSettings, SettingsInput } from '../../../types/management'

export function settingsInput(settings: ManagedSettings): SettingsInput {
  return {
    version: settings.version,
    concurrency: settings.concurrency,
    timeoutSeconds: settings.timeoutSeconds,
    maxUploadBytes: settings.maxUploadBytes,
    defaultSkillIds: { ...settings.defaultSkillIds },
    dingtalk: {
      corpId: settings.dingtalk.corpId,
      appId: settings.dingtalk.appId,
      callbackDomain: settings.dingtalk.callbackDomain
    }
  }
}

export function useSettingsEditor(
  query: { data: Ref<ManagedSettings | undefined>; loading: Ref<boolean>; error: Ref<string>; load: () => Promise<void> },
  persist: (input: SettingsInput) => Promise<ManagedSettings>
) {
  const form = ref<SettingsInput>(), uploadMiB = ref<number | undefined>(10)
  const saving = ref(false), saveError = ref('')
  watch(query.data, value => {
    form.value = value ? settingsInput(value) : undefined
    uploadMiB.value = value ? value.maxUploadBytes / 1024 ** 2 : undefined
  }, { immediate: true, flush: 'sync' })

  async function save(): Promise<boolean> {
    const current = query.data.value, draft = form.value
    if (!current || !draft || saving.value || query.loading.value || query.error.value) return false
    if (current.timeoutCapacity < 60) {
      saveError.value = '部署超时上限低于60秒，请先调整部署配置'
      return false
    }
    saveError.value = ''
    const maxUploadBytes = (uploadMiB.value ?? NaN) * 1024 ** 2
    const ranges = [[draft.concurrency, 1, current.capacity], [draft.timeoutSeconds, 60, current.timeoutCapacity], [maxUploadBytes, 1048576, 10485760]]
    if (ranges.some(([value, min, max]) => !Number.isInteger(value) || value < min || value > max)) {
      saveError.value = `并发需为 1–${current.capacity}，超时为 60–${current.timeoutCapacity} 秒，上传为 1–10 MiB；请填写有效数值。`
      return false
    }
    saving.value = true
    try {
      const input = settingsInput(current)
      input.concurrency = draft.concurrency
      input.timeoutSeconds = draft.timeoutSeconds
      input.maxUploadBytes = maxUploadBytes
      for (const key of ['wallpaper', 'product', 'text'] as const) input.defaultSkillIds[key] = draft.defaultSkillIds[key] || null
      query.data.value = await persist(input)
      return true
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        // 丢弃失效版本；重读失败时也不能继续提交旧配置。
        query.data.value = undefined
        saveError.value = '配置版本已变化，正在重新读取；本次修改未保存。'
        await query.load()
        saveError.value = query.data.value
          ? '配置版本已变化，已读取最新配置；请核对后重新修改并保存。'
          : '配置版本已变化，重新读取失败；请重试加载后再修改。'
      } else {
        saveError.value = reason instanceof Error ? reason.message : '保存失败，请重试'
      }
      return false
    } finally {
      saving.value = false
    }
  }
  return { form, uploadMiB, saving, saveError, save }
}
