<script setup lang="ts">
import { computed, onUnmounted, reactive, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import type { CreativeTool, CreativeTaskDraft } from '@/api/overseas/creative-tools'
import { createRequestKeys, parseCustomTaskInput, taskError, type TasksApi } from '@/api/overseas/tasks'
import { OVERSEAS_LANGUAGES } from '../languages'
import { OVERSEAS_PLATFORMS } from '../platforms'

const props = defineProps<{ tool: CreativeTool; actorId: string; api: TasksApi }>()
const emit = defineEmits<{ close: []; created: [id: string]; failure: [reason: unknown] }>()
const custom = computed(() => props.tool.value === 'custom-size')
const draft = reactive({ sku: '', name: '', language: '', combined: '' })
const errors = reactive({ sku: '', name: '', language: '', combined: '' })
const busy = ref(false), error = ref('')
const keys = createRequestKeys()
let active = true
onUnmounted(() => { active = false })

function payload(): CreativeTaskDraft | undefined {
  const toolKey = props.tool.value
  if (toolKey === 'custom-size') {
    try {
      const { productName, sku } = parseCustomTaskInput(draft.combined.replace(/＋/g, '+'))
      return { toolKey, productNameSku: productName + '+' + sku }
    } catch (reason) {
      errors.combined = reason instanceof Error ? reason.message : '请填写商品名称+SKU'
      return
    }
  }
  const sku = draft.sku.trim(), productName = draft.name.trim()
  errors.sku = sku ? '' : '请填写商品 SKU'
  errors.name = productName ? '' : '请填写品名'
  errors.language = draft.language ? '' : '请选择语言'
  if (errors.sku || errors.name || errors.language) return
  return { toolKey, sku, productName, language: draft.language }
}
async function create() {
  if (busy.value) return
  error.value = ''
  const body = payload()
  if (!body) return
  busy.value = true
  try {
    // Retain the request key across dialog closes or reloads after a lost response.
    const storageKey = JSON.stringify(['hx-creative-request', props.actorId, body])
    const key = sessionStorage.getItem(storageKey) || keys.for(body)
    sessionStorage.setItem(storageKey, key)
    const result = await props.api.createCreative(body, key)
    sessionStorage.removeItem(storageKey)
    if (active) emit('created', result.id)
  } catch (reason) {
    if (!active) return
    error.value = taskError(reason)
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally {
    if (active) busy.value = false
  }
}
</script>

<template>
  <ElDialog :model-value="true" :title="custom ? '新建自定义生图' : tool.label"
    :width="custom ? 'min(420px, calc(100vw - 32px))' : 'min(640px, calc(100vw - 32px))'"
    class="creative-task-dialog" align-center append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @close="emit('close')">
    <ElForm label-position="top" :disabled="busy" @submit.prevent="create">
      <ElFormItem v-if="custom" label="商品名称+SKU" required :error="errors.combined">
        <ElInput v-model="draft.combined" aria-label="商品名称+SKU" placeholder="例如：落地灯+GN-0008" @input="errors.combined = ''" />
      </ElFormItem>
      <div v-else class="dialog-grid">
        <ElFormItem label="商品 SKU" required :error="errors.sku" class="full-row">
          <ElInput v-model="draft.sku" aria-label="商品 SKU" maxlength="80" placeholder="请输入商品 SKU" @input="errors.sku = ''" />
        </ElFormItem>
        <ElFormItem label="目标平台" required :class="{ 'full-row': !tool.brand }">
          <ElSelect :model-value="tool.platform" aria-label="目标平台" disabled>
            <ElOption v-for="option in OVERSEAS_PLATFORMS" :key="option.value" :value="option.value" :label="option.label" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem v-if="tool.brand" label="品牌" required><ElInput :model-value="tool.brand" aria-label="品牌" readonly /></ElFormItem>
        <ElFormItem label="品名" required :error="errors.name">
          <ElInput v-model="draft.name" aria-label="品名" maxlength="80" placeholder="请输入品名" @input="errors.name = ''" />
        </ElFormItem>
        <ElFormItem label="语言" required :error="errors.language">
          <ElSelect v-model="draft.language" aria-label="语言" placeholder="请选择语言" @change="errors.language = ''">
            <ElOption v-for="item in OVERSEAS_LANGUAGES" :key="item.value" :value="item.value" :label="item.label" />
          </ElSelect>
        </ElFormItem>
      </div>
    </ElForm>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer>
      <ElButton :disabled="busy" @click="emit('close')">取消</ElButton>
      <ElButton :loading="busy" type="primary" @click="create">进入 AI 设计工作台</ElButton>
    </template>
  </ElDialog>
</template>
<style scoped>
.dialog-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 20px; }
.full-row { grid-column: 1 / -1; }
.dialog-grid :deep(input[readonly]) { color: var(--el-text-color-secondary); }
:global(.creative-task-dialog) { max-height: calc(100dvh - 32px); overflow-y: auto; }
@media(max-width:600px) { .dialog-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
