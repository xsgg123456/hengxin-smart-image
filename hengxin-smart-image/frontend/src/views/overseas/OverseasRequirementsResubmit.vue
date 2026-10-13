<template>
  <ElAlert class="hx-gap" title="请根据退回意见修改图需" :description="latestReason" type="warning" :closable="false" />
  <OverseasCreate v-model="draft" editing :allowed="allowed" :busy="saving" @back="$emit('close')">
    <template #designer><ElFormItem label="负责设计" required><DesignerPicker v-if="task.capabilities.includes('task.reassign')" v-model="draft.designerId" :api="api" :disabled="saving" @failure="$emit('failure', $event)" /><p class="hx-footnote">当前负责设计：{{ task.designer.name }}</p></ElFormItem></template>
    <template #after>
      <OverseasMaterialsPanel v-model="files" :api="materialsApi" :editable="allowed" replaceable :disabled="saving" @busy="uploading = $event" @failure="$emit('failure', $event)" />
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <div class="hx-filter"><ElButton type="primary" :disabled="!allowed || !ready || uploading" :loading="saving" @click="submit">重新提交设计审核</ElButton><ElButton :disabled="saving" @click="$emit('close')">取消修改</ElButton></div>
    </template>
  </OverseasCreate>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { cleanDraft, createRequestKeys, taskError, validateDraft, type TaskDetail, type TasksApi } from '@/api/overseas/tasks'
import type { Material, MaterialsApi } from '@/api/overseas/materials'
import { resubmitMaterialIds, taskToDraft } from './requirements'
import OverseasCreate from './OverseasCreate.vue'
import DesignerPicker from './DesignerPicker.vue'
import OverseasMaterialsPanel from './OverseasMaterialsPanel.vue'
const props = defineProps<{ task: TaskDetail; materials: Material[]; api: TasksApi; materialsApi: MaterialsApi }>()
const emit = defineEmits<{ changed: [task: TaskDetail]; refresh: []; failure: [reason: unknown]; close: [] }>()
const draft = ref(taskToDraft(props.task)), files = ref([...props.materials]), saving = ref(false), uploading = ref(false), error = ref(''), keys = createRequestKeys()
let active = true
const allowed = computed(() => props.task.status === 'returned' && props.task.capabilities.includes('task.requirements.resubmit'))
const latestReason = computed(() => [...(props.task.requirementsReviews || [])].sort((a, b) => b.version - a.version).find(r => r.decision === 'reject')?.comment || '请核对审核与流转记录中的意见。')
const ready = computed(() => { try { resubmitMaterialIds(files.value, props.task.id); return true } catch { return false } })
async function submit() {
  if (!allowed.value || saving.value || uploading.value) return
  const task = props.task
  error.value = ''
  try {
    validateDraft(draft.value)
    const body = cleanDraft({ ...draft.value, materialIds: resubmitMaterialIds(files.value, task.id) })
    saving.value = true
    const result = await props.api.resubmit(task.id, body, task.version, keys.for({ id: task.id, ...body, version: task.version }))
    if (!active || task.id !== props.task.id) return
    keys.clear(); emit('changed', result)
  } catch (reason) {
    if (!active || task.id !== props.task.id) return
    error.value = taskError(reason)
    if (reason instanceof IdentityError && reason.status === 409) emit('refresh')
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally { if (active) saving.value = false }
}
onUnmounted(() => { active = false })
</script>
