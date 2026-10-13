<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h2>海外 Skill 目录</h2><p>支持完整 Skill ZIP（含参考图和配套文件），工作台可按需选择；历史版本保留。</p></div><div class="hx-admin-toolbar-actions"><ElButton :loading="loading" :disabled="saving" @click="load">刷新 Skill</ElButton><ElButton type="primary" :disabled="loading || !!error || saving" @click="edit()">添加 Skill</ElButton></div></div>
    <div class="hx-filter"><ElInput v-model="search" class="hx-search" aria-label="搜索 Skill" placeholder="搜索 Skill 名称" clearable /><ElSelect v-model="stage" aria-label="Skill 阶段" placeholder="全部阶段" clearable style="width:160px"><ElOption v-for="(label,key) in stages" :key="key" :value="key" :label="label" /></ElSelect></div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <ArtTable :data="rows" :columns="columns" :loading="loading" height="auto" empty-height="280px" :show-table-header="false" :show-pagination="false" empty-text="暂无匹配的 Skill，可添加海外工作流指令">
      <template #stage="{row}">{{ stages[row.stage as Stage] }}</template><template #enabled="{row}"><ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</ElTag></template>
      <template #action="{row}"><ElButton text type="primary" :disabled="saving || loading || !!error" @click="edit(row)">发布新版本</ElButton><ElButton text :disabled="saving || loading" @click="history = row">历史版本</ElButton><ElButton text :disabled="saving || loading || !!error" @click="toggle(row)">{{ row.enabled ? '停用' : '启用' }}</ElButton></template>
    </ArtTable>
  </ElCard>
  <ElDialog v-model="open" :title="form.id ? '发布海外 Skill 新版本' : '添加海外 Skill'" width="min(680px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
    <ElForm label-position="top" :disabled="saving" @submit.prevent="save"><ElFormItem label="Skill 名称" required><ElInput v-model="form.name" aria-label="Skill 名称" :readonly="!!form.id" maxlength="60" /></ElFormItem><ElFormItem label="工作流阶段" required><ElSelect v-model="form.stage" aria-label="工作流阶段" :disabled="!!form.id"><ElOption v-for="(label,key) in stages" :key="key" :value="key" :label="label" /></ElSelect></ElFormItem><ElFormItem label="完整 Skill 包（ZIP）"><input type="file" accept=".zip" aria-label="上传完整 Skill 包" :disabled="saving" @change="selectPackage" /><span v-if="packageFile">{{ packageFile.name }} · 将替换整套文件</span></ElFormItem><ElFormItem label="SKILL.md 指令内容" :required="!packageFile"><ElInput v-model="form.content" aria-label="指令内容" type="textarea" :rows="10" :disabled="!!packageFile" /></ElFormItem></ElForm>
    <ElAlert v-if="formError" :title="formError" type="warning" :closable="false" />
    <template #footer><ElButton :disabled="saving" @click="open = false">取消</ElButton><ElButton v-if="blocked" :loading="loading" :disabled="saving" @click="reconcile">刷新核实并保留草稿</ElButton><ElButton type="primary" :loading="saving" :disabled="blocked || loading" @click="save">发布 Skill</ElButton></template>
  </ElDialog>
  <ElDrawer :model-value="!!history" title="Skill 历史版本" size="min(680px, 100vw)" @close="history = null"><template v-if="history"><h2>{{ history.name }}</h2><ElCollapse><ElCollapseItem v-for="version in history.versions" :key="version.version" :name="version.version" :title="'版本 ' + version.version + ' · ' + version.createdAt"><p v-if="version.assetNames?.length">配套资源：{{ version.assetNames.join("、") }}</p><div v-for="(content,path) in version.files" :key="path"><h3>{{ path }}</h3><pre style="white-space:pre-wrap;overflow-wrap:anywhere">{{ content }}</pre></div></ElCollapseItem></ElCollapse></template></ElDrawer>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { IdentityError } from '@/api/identity/auth'
import { stages, managementError, type Stage, type Skill, type ManagementApi } from '@/api/overseas/management'
const props = defineProps<{api: ManagementApi}>()
const emit = defineEmits<{failure:[reason: unknown]}>()
const skills = ref<Skill[]>([]), history = ref<Skill|null>(null), search = ref(''), stage = ref(''), error = ref(''), formError = ref(''), loading = ref(false), saving = ref(false), open = ref(false), blocked = ref(false)
const blank = () => ({ id:'', name:'', stage:'analysis' as Stage, content:'', version:1, files:{} as Record<string,string> })
const form = reactive(blank())
const packageFile = ref<File | null>(null)
function selectPackage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.zip') || file.size > 20 * 1024 * 1024) { formError.value = '请上传不超过20 MiB的ZIP文件'; return }
  packageFile.value = file; formError.value = ''
}
let active = true
const rows = computed(() => skills.value.filter(s => (!stage.value || s.stage === stage.value) && s.name.toLowerCase().includes(search.value.trim().toLowerCase())))
function failure(reason: unknown) { if (reason instanceof IdentityError && [401,403].includes(reason.status)) { skills.value = []; history.value = null; open.value = false; Object.assign(form,blank()); emit('failure',reason) } }
async function load() {
  if (loading.value) return false
  loading.value = true; error.value = ''; history.value = null
  try { const result = await props.api.skills(); if (!active) return false; skills.value = result.items; return true }
  catch (reason) { if (active) { skills.value = []; error.value = managementError(reason); failure(reason) }; return false }
  finally { if (active) loading.value = false }
}
function edit(skill?: Skill) {
  packageFile.value = null
  const files = skill?.versions.find(v => v.version === skill.currentVersion)?.files || {}
  Object.assign(form, skill ? {id:skill.id,name:skill.name,stage:skill.stage,version:skill.version,content:files['SKILL.md'] || '',files:{...files}} : blank())
  blocked.value = false; formError.value = ''; open.value = true
}
async function reconcile() {
  if (!await load() || !active || !open.value) return
  if (packageFile.value) { formError.value = '目录已刷新，请关闭表单核对历史版本后再操作，避免重复发布'; return }
  const latest = skills.value.find(s => form.id ? s.id === form.id : s.name === form.name.trim())
  if (latest && latest.stage !== form.stage) { blocked.value = true; formError.value = '服务端同名 Skill 属于其他阶段，请关闭表单后核对目录'; return }
  const files = { ...form.files, 'SKILL.md': form.content }
  if (latest && latest.versions.some(v => Object.keys(v.files).length === Object.keys(files).length && Object.entries(files).every(([path,content]) => v.files[path] === content))) {
    formError.value = '服务端已存在相同内容版本，无需重复发布。请关闭表单查看历史版本。'; blocked.value = true; return
  }
  if (latest) { form.id = latest.id; form.version = latest.version }
  blocked.value = false; formError.value = '最新版本已核实，草稿保留；请核对后发布'
}
async function save() {
  if (saving.value || blocked.value || loading.value) return
  if (!form.name.trim() || (!packageFile.value && !form.content.trim())) { formError.value = '请填写 Skill 名称和指令内容'; return }
  saving.value = true; formError.value = ''
  try { const files = {...form.files,'SKILL.md':form.content}; if (packageFile.value) await props.api.uploadPackage(packageFile.value,form.name.trim(),form.stage,form.id || undefined,form.id ? form.version : undefined); else if (form.id) await props.api.publish(form.id,form.version,files); else await props.api.createSkill(form.name.trim(),form.stage,files); if (active) { open.value = false; ElMessage.success('Skill 已发布'); await load() } }
  catch (reason) { if (active) { formError.value = managementError(reason); failure(reason); if (reason instanceof IdentityError && (reason.status === 409 || reason.status === 0 || reason.status >= 500)) { blocked.value = true; formError.value = reason.status === 409 ? '版本已变化，草稿保留；请刷新核实后再发布' : '写入结果未知；请刷新核实，避免重复发布' } } }
  finally { if (active) saving.value = false }
}
async function toggle(skill: Skill) {
  if (saving.value || loading.value) return
  if (skill.enabled) { try { await ElMessageBox.confirm('停用后，仍绑定此 Skill 的新作业将被拒绝；历史作业不受影响。', '停用 Skill', {type:'warning',confirmButtonText:'确认停用',cancelButtonText:'取消'}) } catch { return } }
  if (!active) return
  saving.value = true
  try { await props.api.toggle(skill.id,skill.version,!skill.enabled); if (active) await load() }
  catch (reason) { if (active) { failure(reason); await load(); error.value = managementError(reason) + '；已刷新，请核对当前状态' } }
  finally { if (active) saving.value = false }
}
const columns = [{prop:'name',label:'Skill 名称',minWidth:180},{prop:'stage',label:'工作流阶段',minWidth:120,useSlot:true},{prop:'currentVersion',label:'当前版本',width:100},{prop:'enabled',label:'状态',width:90,useSlot:true},{prop:'action',label:'操作',minWidth:270,useSlot:true}]
onMounted(load)
onUnmounted(() => { active = false; skills.value = []; history.value = null; Object.assign(form,blank()) })
</script>
