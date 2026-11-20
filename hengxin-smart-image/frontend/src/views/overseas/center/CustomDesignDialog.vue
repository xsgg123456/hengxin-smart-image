<template>
  <ElDialog :model-value="true" title="新建自定义生图" width="min(420px, calc(100vw - 32px))"
    align-center append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy"
    :show-close="!busy" @close="emit('close')">
    <ElForm label-position="top" :disabled="busy" @submit.prevent="submit">
      <ElFormItem label="商品名称+SKU" required :error="error">
        <ElInput v-model="value" aria-label="商品名称+SKU" placeholder="例如：落地灯+GN-0008" @input="error=''" />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton :disabled="busy" @click="emit('close')">取消</ElButton>
      <ElButton type="primary" :loading="busy" @click="submit">进入 AI 设计工作台</ElButton>
    </template>
  </ElDialog>
</template>
<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { createRequestKeys, parseCustomTaskInput } from '@/api/overseas/tasks'
const props = defineProps<{
  actorId: string
  create: (value: string, key: string) => Promise<{ id: string }>
}>()
const emit = defineEmits<{ close: []; created: [id: string]; failure: [reason: unknown] }>()
const value = ref(''), error = ref(''), busy = ref(false)
const keys = createRequestKeys()
let active = true
onUnmounted(() => { active = false })

async function submit() {
  if (busy.value) return
  error.value = ''
  try {
    const { productName, sku } = parseCustomTaskInput(value.value)
    const normalized = productName + '+' + sku
    // Keep the key through an ambiguous network failure, even if the dialog is reopened.
    const storageKey = JSON.stringify(['hx-custom-design', props.actorId, normalized])
    const key = sessionStorage.getItem(storageKey) || keys.for(normalized)
    sessionStorage.setItem(storageKey, key)
    busy.value = true
    const result = await props.create(normalized, key)
    if (!active) return
    sessionStorage.removeItem(storageKey)
    keys.clear()
    emit('created', result.id)
  } catch (reason) {
    if (!active) return
    error.value = reason instanceof Error ? reason.message : '创建失败，请重试'
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally {
    if (active) busy.value = false
  }
}
</script>
