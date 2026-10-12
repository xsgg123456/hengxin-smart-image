<template>
  <div class="hx-stack">
    <ElInput v-model="search" placeholder="搜索设计姓名或部门" aria-label="搜索负责设计" clearable :disabled="disabled" maxlength="100" />
    <ElSelect :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" aria-label="负责设计" placeholder="请选择负责设计" :loading="busy" :disabled="disabled || busy || !!error" style="width: 100%">
      <ElOption v-for="person in candidates" :key="person.id" :value="person.id" :label="`${person.name} · ${person.department || '未设置部门'}`" />
    </ElSelect>
    <p v-if="busy" role="status">正在加载设计人选…</p>
    <ElAlert v-else-if="error" :title="error" type="error" :closable="false" />
    <p v-else-if="!candidates.length" class="hx-muted">暂无可用设计，请调整搜索或联系管理员。</p>
    <div class="hx-filter"><ElButton :disabled="disabled || busy" @click="load">刷新设计人选</ElButton><ElPagination v-if="total > size" small layout="prev, pager, next" :current-page="page" :page-size="size" :total="total" :disabled="disabled || busy" @current-change="page = $event" /></div>
  </div>
</template>
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { taskError, type TasksApi, type Designer } from '@/api/overseas/tasks'
const props = defineProps<{ api: TasksApi; modelValue: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; failure: [reason: unknown] }>()
const search = ref(''), page = ref(1), size = 20, total = ref(0), candidates = ref<Designer[]>([]), busy = ref(false), error = ref('')
let generation = 0, timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  const current = ++generation; busy.value = true; error.value = ''; candidates.value = []; total.value = 0
  try { const result = await props.api.designers({ search: search.value.trim(), page: page.value, pageSize: size }); if (current !== generation) return; candidates.value = result.items; total.value = result.total }
  catch (reason) { if (current !== generation) return; error.value = taskError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) }
  finally { if (current === generation) busy.value = false }
}
watch(search, () => { ++generation; candidates.value = []; total.value = 0; busy.value = true; clearTimeout(timer); timer = setTimeout(() => { if (page.value !== 1) page.value = 1; else void load() }, 250) })
watch(page, load, { immediate: true })
onUnmounted(() => { ++generation; clearTimeout(timer) })
</script>
