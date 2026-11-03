<template>
  <div class="hx-stack designer-picker">
    <ElSelect :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" aria-label="负责设计" placeholder="请选择负责设计" :loading="busy" :disabled="disabled || busy" style="width: 100%">
      <ElOption v-for="person in options" :key="person.id" :value="person.id" :label="person.name" />
    </ElSelect>
    <p v-if="busy" role="status">正在加载设计人选…</p>
    <ElAlert v-else-if="error" :title="error" type="error" :closable="false" />
    <p v-else-if="!candidates.length" class="hx-muted">暂无可用设计，请联系管理员。</p>
    <div class="hx-filter"><ElButton :disabled="disabled || busy" @click="load">刷新设计人选</ElButton><ElPagination v-if="total > size" small layout="prev, pager, next" :current-page="page" :page-size="size" :total="total" :disabled="disabled || busy" @current-change="page = $event" /></div>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { taskError, type TasksApi, type Designer } from '@/api/overseas/tasks'
const props = defineProps<{ api: TasksApi; modelValue: string; disabled?: boolean; selected?: Designer | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; failure: [reason: unknown] }>()
const page = ref(1), size = 20, total = ref(0), candidates = ref<Designer[]>([]), busy = ref(false), error = ref('')
const retained = ref<Designer>()
const options = computed(() => { const chosen = props.selected?.id === props.modelValue ? props.selected : retained.value; return chosen && !candidates.value.some(p => p.id === chosen.id) ? [chosen, ...candidates.value] : candidates.value })
let generation = 0, selectionGeneration = 0
watch(() => props.modelValue, async id => {
  const current = ++selectionGeneration
  if (!id) { retained.value = undefined; return }
  const found = candidates.value.find(p => p.id === id) || (props.selected?.id === id ? props.selected : undefined)
  if (found) { retained.value = found; return }
  try {
    let n = 1, count = 1
    while (n <= count && current === selectionGeneration) {
      const result = await props.api.designers({ search: '', page: n, pageSize: size })
      if (current !== selectionGeneration) return
      const person = result.items.find(p => p.id === id)
      if (person) { retained.value = person; return }
      count = Math.ceil(result.total / size); n++
    }
    if (current === selectionGeneration) { retained.value = undefined; error.value = '原负责设计已不可选，请重新选择。' }
  } catch (reason) { if (current === selectionGeneration) { error.value = taskError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) } }
}, { immediate: true })
async function load() {
  const current = ++generation; busy.value = true; error.value = ''; candidates.value = []; total.value = 0
  try { const result = await props.api.designers({ search: '', page: page.value, pageSize: size }); if (current !== generation) return; candidates.value = result.items; total.value = result.total }
  catch (reason) { if (current !== generation) return; error.value = taskError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) }
  finally { if (current === generation) busy.value = false }
}
watch(page, load, { immediate: true })
onUnmounted(() => { ++generation; ++selectionGeneration })
</script>

<style scoped>
.designer-picker { width: 100%; min-width: 0; }
</style>
