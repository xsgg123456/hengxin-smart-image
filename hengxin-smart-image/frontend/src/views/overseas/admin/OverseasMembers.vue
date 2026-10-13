<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head">
      <div><span class="hx-admin-kicker">MEMBER ACCESS</span><h2>海外成员目录</h2>
        <p>{{ adapter.preview ? '配置仅用于本地管理交互预览。' : '成员身份来自企业钉钉，姓名只读；可兼任多个海外角色。' }}</p></div>
      <ElButton v-if="adapter.preview" type="primary" @click="edit()">新增成员</ElButton>
    </div>
    <div class="hx-filter">
      <ElInput v-model="query.search" class="hx-search" placeholder="搜索姓名" maxlength="100" clearable aria-label="搜索成员" @change="filter" />
      <ElSelect v-model="query.status" clearable placeholder="全部状态" aria-label="成员状态筛选" style="width: 150px" @change="filter"><ElOption v-for="(label,key) in statuses" :key="key" :value="key" :label="label" /></ElSelect>
      <ElSelect v-model="query.role" clearable placeholder="全部角色" aria-label="成员角色筛选" style="width: 150px" @change="filter"><ElOption v-for="(label,key) in roleOptions" :key="key" :value="key" :label="label" /></ElSelect>
      <ElButton :loading="loading" @click="load">刷新成员</ElButton>
    </div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon class="hx-gap" />
    <ElButton v-if="error" class="hx-gap" @click="load">重试</ElButton>
    <ArtTable height="auto" empty-height="280px" :data="rows" :columns="columns" :loading="loading" :show-table-header="false" :show-pagination="false" empty-text="暂无符合条件的海外成员">
      <template #roles="{ row }">{{ row.roles.map((r: MemberRole) => memberRoles[r]).join('、') || '待授权' }}</template>
      <template #status="{ row }"><ElTag :type="row.status === 'active' ? 'success' : 'info'">{{ statuses[row.status as MemberStatus] }}</ElTag></template>
      <template #action="{ row }"><ElButton text type="primary" :disabled="loading || saving || !!error" @click="edit(row)">编辑</ElButton><ElButton v-if="adapter.preview" text :disabled="loading" @click="toggle(row)">{{ row.status === 'active' ? '禁用' : '启用' }}</ElButton><ElButton v-if="adapter.remove" text type="danger" @click="remove(row)">删除</ElButton></template>
    </ArtTable>
    <div class="hx-filter hx-gap"><span>共 {{ total }} 位成员</span><ElPagination :current-page="query.page" :page-size="query.pageSize" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="pageChanged" />
      <ElSelect v-model="query.pageSize" aria-label="每页成员数" style="width: 110px" @change="filter"><ElOption v-for="size in [20,50,100]" :key="size" :value="size" :label="`${size}条/页`" /></ElSelect></div>
  </ElCard>
  <ElDialog v-model="open" :title="form.id ? '编辑海外成员' : '新增海外成员'" width="min(480px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
    <ElForm label-position="top" @submit.prevent="save">
      <ElFormItem label="姓名" required><ElInput v-model="form.name" aria-label="成员姓名" :readonly="!adapter.preview" maxlength="40" /></ElFormItem>
      <ElFormItem label="海外业务角色" required><ElSelect v-model="form.roles" multiple :multiple-limit="adapter.preview ? 1 : 0" aria-label="海外业务角色" :disabled="saving || conflict"><ElOption v-for="(label,key) in roleOptions" :key="key" :label="label" :value="key" /></ElSelect></ElFormItem>
      <ElFormItem label="账号启用"><ElSwitch :model-value="form.status === 'active'" aria-label="账号启用" :disabled="saving || conflict" @change="form.status = $event ? 'active' : 'disabled'" /><span v-if="form.status === 'pending'" class="hx-muted">待授权，请明确启用或禁用</span></ElFormItem>
    </ElForm>
    <ElAlert v-if="formError" :title="formError" type="error" :closable="false" />
    <template #footer><ElButton :disabled="saving" @click="open = false">取消</ElButton><ElButton v-if="conflict" :loading="saving" @click="refreshEdit">刷新最新资料</ElButton><ElButton type="primary" :loading="saving" :disabled="conflict" @click="save">保存成员</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { memberRoles, type MembersAdapter, type OverseasMember, type MemberRole, type MemberStatus } from '@/api/overseas/members'
import { IdentityError } from '@/api/identity/auth'
const props = defineProps<{ adapter: MembersAdapter }>()
const emit = defineEmits<{ changed: []; failure: [reason: unknown] }>()
const query = reactive({ search: '', status: '', role: '', page: 1, pageSize: 20 })
const rows = ref<OverseasMember[]>([]), total = ref(0), loading = ref(false), saving = ref(false)
const open = ref(false), error = ref(''), formError = ref(''), conflict = ref(false)
const statuses = { active: '启用', pending: '待授权', disabled: '禁用' }
const roleOptions = computed(() => props.adapter.preview ? { operator: '运营', designer: '设计', super_admin: '管理员' } : memberRoles)
const blank = (): OverseasMember => ({ id: '', name: '', department: '', roles: ['operator'], status: 'active', version: 1, createdAt: '', updatedAt: '' })
const form = reactive(blank())
let generation = 0, active = true, confirmingDisable = false, originalStatus: MemberStatus = 'active'
function failure(reason: unknown) {
  if (!active) return
  error.value = reason instanceof Error ? reason.message : '成员加载失败，请重试'
  rows.value = []; total.value = 0; open.value = false
  emit('failure', reason)
}
async function load() {
  const epoch = ++generation
  loading.value = true; error.value = ''; rows.value = []
  try { const result = await props.adapter.list({ ...query }); if (active && epoch === generation) { rows.value = result.items; total.value = result.total } }
  catch (reason) { if (epoch === generation) failure(reason) }
  finally { if (active && epoch === generation) loading.value = false }
}
function filter() { query.page = 1; void load() }
function pageChanged(page: number) { query.page = page; void load() }
async function edit(member?: OverseasMember) {
  if (loading.value || saving.value) return
  saving.value = true; formError.value = ''; conflict.value = false
  try { const value = member ? await props.adapter.get(member.id) : blank(); if (!active) return; Object.assign(form, value, { roles: [...value.roles] }); originalStatus = value.status; open.value = true }
  catch (reason) { failure(reason) } finally { saving.value = false }
}
async function refreshEdit() { await edit({ ...form }); }
async function save() {
  if (saving.value || conflict.value) return
  formError.value = ''
  if (form.status === 'pending' || (form.status === 'active' && !form.roles.length)) { formError.value = '请选择启用或禁用；启用成员至少需要一个角色'; return }
  saving.value = true
  try {
    if (form.status === 'disabled' && originalStatus !== 'disabled') {
      confirmingDisable = true
      try { await ElMessageBox.confirm(`禁用「${form.name}」后将撤销其全部海外会话，是否继续？`, '禁用成员', { type: 'warning', confirmButtonText: '确认禁用', cancelButtonText: '取消' }) } catch { return }
      finally { confirmingDisable = false }
    }
    if (!active) return
    await props.adapter.save({ ...form, roles: [...form.roles] })
    if (!active) return
    open.value = false; emit('changed'); ElMessage.success(props.adapter.preview ? '成员已保存到本地预览' : '成员已保存'); await load()
  } catch (reason) {
    if (!active) return
    if (reason instanceof IdentityError && (reason.status === 409 || reason.status === 422)) { formError.value = reason.message; conflict.value = reason.status === 409 }
    else if (props.adapter.preview) formError.value = reason instanceof Error ? reason.message : '保存失败'
    else failure(reason)
  } finally { saving.value = false }
}
async function toggle(member: OverseasMember) { await edit(member); if (!open.value) return; form.status = member.status === 'active' ? 'disabled' : 'active'; await save() }
async function remove(member: OverseasMember) {
  try { await ElMessageBox.confirm(`删除「${member.name}」？此操作仅移除本地预览成员。`, '删除成员', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }); await props.adapter.remove?.(member.id); await load() } catch { /* 取消 */ }
}
const columns = [{ prop: 'name', label: '姓名', minWidth: 110 }, { prop: 'roles', label: '海外角色', minWidth: 180, useSlot: true }, { prop: 'status', label: '状态', width: 90, useSlot: true }, { prop: 'action', label: '操作', width: props.adapter.preview ? 220 : 90, useSlot: true }]
onMounted(load)
onUnmounted(() => { active = false; ++generation; if (confirmingDisable) ElMessageBox.close() })
</script>
