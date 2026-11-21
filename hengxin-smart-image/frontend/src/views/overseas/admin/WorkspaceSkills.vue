<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { CREATIVE_TOOLS, type CreativeTool } from '@/api/overseas/creative-tools'
import type { ManagementApi, ToolBindings } from '@/api/overseas/management'

const props = defineProps<{ api: Pick<ManagementApi, 'toolBindings' | 'setToolBindings'> }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const catalog = ref<ToolBindings>()
const editing = ref<CreativeTool>()
const draft = ref<string[]>([]), query = ref(''), error = ref(''), dialogError = ref('')
const loading = ref(false), saving = ref(false)
const options = computed(() => {
  const term = query.value.trim().toLowerCase()
  return catalog.value?.items.filter(s => [s.name, s.displayName].some(name => name.toLowerCase().includes(term))) || []
})
function bound(tool: CreativeTool) {
  const ids = catalog.value?.bindings[tool.value] || []
  return catalog.value?.items.filter(skill => ids.includes(skill.id)) || []
}
function failure(reason: unknown) {
  if (reason instanceof IdentityError && [401, 403].includes(reason.status)) {
    catalog.value = undefined
    editing.value = undefined
    emit('failure', reason)
  }
  return reason instanceof IdentityError && typeof reason.detail === 'string' ? reason.detail :
    reason instanceof Error ? reason.message : '工作台绑定暂不可用'
}
async function load() {
  loading.value = true
  error.value = ''
  try { catalog.value = await props.api.toolBindings() }
  catch (reason) { error.value = failure(reason) }
  finally { loading.value = false }
}
function edit(tool: CreativeTool) {
  if (!catalog.value) return
  draft.value = [...catalog.value.bindings[tool.value]]
  query.value = ''
  dialogError.value = ''
  editing.value = tool
}
async function save() {
  if (!editing.value || !catalog.value || saving.value) return
  const key = editing.value.value
  saving.value = true
  dialogError.value = ''
  try {
    catalog.value = await props.api.setToolBindings(key, catalog.value.bindings[key], draft.value)
    editing.value = undefined
    ElMessage.success('工作台绑定已保存')
  } catch (reason) {
    dialogError.value = failure(reason)
    if (reason instanceof IdentityError && [409, 422].includes(reason.status)) {
      editing.value = undefined
      await load()
      if (!error.value) error.value = dialogError.value
    }
  } finally { saving.value = false }
}
onMounted(load)
</script>
<template>
  <ElCard class="art-card" shadow="never">
    <div class="scope-note"><span>每张卡片独立绑定 Skill。工作台仅提供已绑定且已开启的 Skill。</span>
      <ElButton :loading="loading" :disabled="saving || !!editing" @click="load">刷新绑定</ElButton></div>
    <ElAlert v-if="error" :title="error" type="warning" :closable="false" />
    <ElTable v-if="catalog" :data="[...CREATIVE_TOOLS]" row-key="value" v-loading="loading">
      <ElTableColumn prop="label" label="工作台" min-width="180" />
      <ElTableColumn label="已绑定 Skill" min-width="145"><template #default="{row}">
        <div class="tags"><ElTag v-for="s in bound(row)" :key="s.id" :type="s.enabled ? 'primary' : 'info'">{{ s.displayName }}{{ s.enabled ? '' : '（已关闭）' }}</ElTag>
          <span v-if="!bound(row).length" class="hx-muted">未绑定</span></div>
      </template></ElTableColumn>
      <ElTableColumn label="操作" width="110"><template #default="{row}"><ElButton type="primary" text :disabled="loading || saving" @click="edit(row)">设置绑定</ElButton></template></ElTableColumn>
    </ElTable>
  </ElCard>
  <ElDialog v-if="editing" :model-value="true" :title="'设置绑定 · ' + editing.label" width="min(560px, 94vw)" append-to-body
    :show-close="!saving" :close-on-click-modal="!saving" :close-on-press-escape="!saving" @close="editing = undefined">
    <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" />
    <ElInput v-model="query" placeholder="搜索已安装的 Skill" clearable aria-label="搜索已安装的 Skill" />
    <ElCheckboxGroup v-model="draft" class="choices" :disabled="saving">
      <ElCheckbox v-for="s in options" :key="s.id" :value="s.id">{{ s.displayName }}{{ s.enabled ? '' : '（已关闭）' }}</ElCheckbox>
      <ElEmpty v-if="!options.length" description="暂无匹配的 Skill" />
    </ElCheckboxGroup>
    <template #footer><ElButton :disabled="saving" @click="editing = undefined">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存绑定</ElButton></template>
  </ElDialog>
</template>
<style scoped>
.scope-note{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 18px;color:var(--el-text-color-secondary)}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.choices{display:grid;max-height:44vh;overflow:auto;margin-top:14px}
.choices .el-checkbox{height:auto;min-height:38px;margin:0}
.choices :deep(.el-checkbox__label){white-space:normal;overflow-wrap:anywhere}
</style>
