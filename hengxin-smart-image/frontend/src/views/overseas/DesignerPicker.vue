<template>
  <div class="hx-stack designer-picker">
    <ElSelect :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" aria-label="负责设计" placeholder="请选择负责设计" :loading="busy" :disabled="disabled || busy || !!error" style="width: 100%">
      <ElOption v-for="person in candidates" :key="person.id" :value="person.id" :label="person.name" />
    </ElSelect>
    <p v-if="busy" role="status">正在加载设计人选…</p>
    <ElAlert v-else-if="error" :title="error" type="error" :closable="false" />
    <p v-else-if="!candidates.length" class="hx-muted">暂无可用设计，请联系管理员。</p>
    <div class="hx-filter"><ElButton :disabled="disabled || busy" @click="load">刷新设计人选</ElButton><ElPagination v-if="total > size" small layout="prev, pager, next" :current-page="page" :page-size="size" :total="total" :disabled="disabled || busy" @current-change="page = $event" /></div>
  </div>
</template>
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { taskError, type TasksApi, type Designer } from '@/api/overseas/tasks'
const props = defineProps<{ api: TasksApi; modelValue: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; failure: [reason: unknown] }>()
const page = ref(1), size = 20, total = ref(0), candidates = ref<Designer[]>([]), busy = ref(false), error = ref('')
let generation = 0
async function load() {
  const current = ++generation; busy.value = true; error.value = ''; candidates.value = []; total.value = 0
  try { const result = await props.api.designers({ search: '', page: page.value, pageSize: size }); if (current !== generation) return; candidates.value = result.items; total.value = result.total }
  catch (reason) { if (current !== generation) return; error.value = taskError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) }
  finally { if (current === generation) busy.value = false }
}
watch(page, load, { immediate: true })
onUnmounted(() => { ++generation })
</script>

<style scoped>
.designer-picker { width: 100%; min-width: 0; }
</style>
