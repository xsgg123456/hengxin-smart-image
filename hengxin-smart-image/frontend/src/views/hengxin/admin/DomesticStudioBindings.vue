<template>
  <ElCard shadow="never" class="art-card hx-section domestic-bindings">
    <div class="hx-admin-section-head"><div><h2>工作台可选 Skill</h2><p>绑定后供用户选择，仅在本轮勾选时使用。</p></div><ElButton type="primary" :loading="saving" :disabled="loading || !!error || !dirty" @click="save">保存绑定</ElButton></div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton :loading="loading" @click="load">重试</ElButton></ElAlert>
    <p v-if="loading" role="status">正在加载工作台绑定…</p>
    <div v-if="!loading && !error" class="domestic-binding-list"><div v-for="workspace in workspaces" :key="workspace.key" class="domestic-binding-row"><div><small>{{ workspace.group }}</small><strong>{{ workspace.title }}</strong></div><ElSelect v-model="draft[workspace.key]" clearable filterable :disabled="saving" :aria-label="`${workspace.title}绑定 Skill`" placeholder="未绑定" @clear="draft[workspace.key] = null"><ElOption v-for="skill in enabledSkills" :key="skill.id" :value="skill.id" :label="skill.displayName" /><ElOption v-if="missing(workspace.key)" :value="draft[workspace.key]!" label="已绑定 Skill 不可用，请重新选择" disabled /></ElSelect><ElTag :type="draft[workspace.key] && !missing(workspace.key) ? 'success' : 'warning'" size="small">{{ missing(workspace.key) ? '不可用' : draft[workspace.key] ? '用户选用' : '未配置' }}</ElTag></div></div>
    <p class="hx-footnote">未绑定或 Skill 不可用时，仍可正常对话和改图。</p>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import type { ManagedSkill } from '@/api/shared/skill-types'
import type { DomesticStudioSkillsApi, WorkspaceBindings, WorkspaceKey } from '@/api/hengxin/domestic-studio-skills'
import { domesticWorkspaces as workspaces } from '@/api/hengxin/domestic-workspaces'
const props = defineProps<{ api: DomesticStudioSkillsApi }>()
const emit = defineEmits<{ failure: [reason: unknown]; saved: [bindings: WorkspaceBindings]; saving: [active: boolean] }>()
const blank = (): WorkspaceBindings => ({ camera: null, case: null, product: null, scene: null, phone: null })
const draft = ref<WorkspaceBindings>(blank()), saved = ref<WorkspaceBindings>(blank()), skills = ref<ManagedSkill[]>([])
const loading = ref(false), saving = ref(false), error = ref('')
const enabledSkills = computed(() => skills.value.filter(skill => skill.enabled))
const missing = (key: WorkspaceKey) => !!draft.value[key] && !enabledSkills.value.some(skill => skill.id === draft.value[key])
const dirty = computed(() => workspaces.some(item => draft.value[item.key] !== saved.value[item.key]))
async function load() {
  if (loading.value || saving.value) return
  loading.value = true; error.value = ''
  try { const [bindings, catalog] = await Promise.all([props.api.getBindings(), props.api.skills()]); saved.value = { ...bindings.bindings }; draft.value = { ...bindings.bindings }; skills.value = catalog.items }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '加载绑定失败'; emit('failure', reason) }
  finally { loading.value = false }
}
async function save() {
  if (saving.value || loading.value || error.value || !dirty.value) return
  if (workspaces.some(item => missing(item.key))) { ElMessage.warning('请选择可用的 Skill 或解除绑定'); return }
  saving.value = true; emit('saving', true)
  try { const response = await props.api.setBindings({ ...draft.value }, { ...saved.value }); saved.value = { ...response.bindings }; draft.value = { ...response.bindings }; emit('saved', { ...response.bindings }); ElMessage.success('绑定已保存') }
  catch (reason) { error.value = reason instanceof IdentityError && typeof reason.detail === 'string' ? reason.detail : reason instanceof Error ? `${reason.message}；请重新加载后核对绑定` : '保存结果未确认，请重新加载'; emit('failure', reason) }
  finally { saving.value = false; emit('saving', false) }
}
onMounted(load)
</script>
<style scoped>
.domestic-bindings { border:0 !important; box-shadow:none; }
.domestic-bindings :deep(.el-card__body) { padding:0; }
.domestic-bindings .hx-admin-section-head { align-items:center; margin:18px 0 10px; }
.domestic-bindings .hx-admin-section-head h2 { margin:0; font-size:18px; font-weight:400; }
.domestic-bindings .hx-admin-section-head p { margin:8px 0 0; color:var(--art-gray-500); font-size:13px; line-height:1.5; }
.domestic-binding-row { display:flex; align-items:center; gap:24px; padding:22px 0; border-bottom:1px solid var(--default-border); }
.domestic-binding-row > div:first-child { width:320px; flex-shrink:0; }
.domestic-binding-row small,.domestic-binding-row strong { display:block; }
.domestic-binding-row small { margin-bottom:5px; color:var(--art-gray-500); font-size:12px; }
.domestic-binding-row .el-select { width:460px; max-width:50%; }
.domestic-binding-row :deep(.el-select__wrapper) { min-height:32px; }
.domestic-bindings .hx-footnote { margin-top:16px; font-size:12px; line-height:1.8; }
@media (max-width:800px) { .domestic-binding-row { flex-wrap:wrap; } .domestic-binding-row > div:first-child { width:100%; } .domestic-binding-row .el-select { max-width:80%; } }
</style>
