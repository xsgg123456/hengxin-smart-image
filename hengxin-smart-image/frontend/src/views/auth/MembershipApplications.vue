<template>
  <div>
    <p class="hx-footnote">仅显示用户主动提交给{{ businessName }}业务的申请；审批通过后加入本业务成员目录。</p>
    <div class="hx-filter">
      <ElInput v-model="query.search" class="hx-search" clearable maxlength="100" placeholder="搜索申请人姓名" aria-label="搜索申请人" @change="filter" />
      <ElSelect v-model="query.status" clearable placeholder="全部申请状态" aria-label="申请状态" style="width: 160px" @change="filter"><ElOption v-for="(label, key) in applicationStatuses" :key="key" :label="label" :value="key" /></ElSelect>
      <ElButton :loading="loading" @click="load">刷新申请</ElButton>
    </div>
    <ElAlert v-if="error" class="hx-gap" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载申请</ElButton></ElAlert>
    <ArtTable height="auto" empty-height="280px" :data="rows" :columns="columns" :loading="loading" :show-table-header="false" :show-pagination="false" empty-text="暂无符合条件的加入申请">
      <template #status="{ row }"><ElTag :type="row.status === 'pending' ? 'warning' : 'info'">{{ applicationStatuses[row.status as MembershipApplication['status']] }}</ElTag></template>
      <template #createdAt="{ row }">{{ new Date(row.createdAt).toLocaleString('zh-CN') }}</template>
      <template #reason="{ row }">{{ row.reason || '—' }}</template>
      <template #action="{ row }"><ElButton v-if="row.status === 'pending'" text type="primary" :disabled="loading || saving" @click="edit(row)">审批申请</ElButton><span v-else class="hx-muted">已结束</span></template>
    </ArtTable>
    <div class="hx-filter hx-gap"><span>{{ loading ? '正在读取申请…' : `共 ${total} 条申请` }}</span><ElPagination :current-page="query.page" :page-size="query.pageSize" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="pageChanged" /></div>
    <ElDialog v-model="open" :title="`审批${businessName}业务加入申请`" width="min(480px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <ElForm label-position="top" :disabled="saving || conflict">
        <ElFormItem label="申请人">{{ selected?.name }}</ElFormItem>
        <ElFormItem label="审批结果" required><ElRadioGroup v-model="decision"><ElRadio value="approve">通过</ElRadio><ElRadio value="reject">拒绝</ElRadio></ElRadioGroup></ElFormItem>
        <ElFormItem v-if="decision === 'approve'" :label="`${businessName}业务角色`" required><ElSelect v-model="role" clearable aria-label="审批业务角色" placeholder="请选择本业务角色"><ElOption v-for="(label, key) in roles" :key="key" :label="label" :value="key" /></ElSelect></ElFormItem>
        <ElFormItem v-else label="拒绝原因" required><ElInput v-model="reason" type="textarea" maxlength="1000" show-word-limit aria-label="拒绝原因" /></ElFormItem>
      </ElForm>
      <ElAlert v-if="formError" :title="formError" type="error" :closable="false" />
      <template #footer><ElButton :disabled="saving" @click="open = false">取消</ElButton><ElButton v-if="conflict" @click="refreshConflict">刷新最新申请</ElButton><ElButton type="primary" :loading="saving" :disabled="conflict" @click="save">确认审批</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { applicationStatuses, type ApplicationsAdapter, type MembershipApplication } from '@/api/identity/applications'
const props = defineProps<{ adapter: ApplicationsAdapter; businessName: string; roles: Record<string, string> }>()
const emit = defineEmits<{ changed: []; failure: [reason: unknown] }>()
const query = reactive({ search: '', status: 'pending', page: 1, pageSize: 20 })
const rows = ref<MembershipApplication[]>([]), total = ref(0), loading = ref(false), error = ref('')
const selected = ref<MembershipApplication>(), open = ref(false), saving = ref(false), conflict = ref(false), formError = ref('')
const decision = ref<'approve' | 'reject'>('approve'), role = ref(''), reason = ref('')
let generation = 0, active = true, confirming = false
const statusOf = (value: unknown) => value && typeof value === 'object' && 'status' in value ? value.status : undefined
function failed(value: unknown) {
  error.value = value instanceof Error ? value.message : '申请读取失败，请重试'
  rows.value = []; total.value = 0
  if ([401, 403].includes(Number(statusOf(value)))) { open.value = false; selected.value = undefined; emit('failure', value) }
}
async function load() {
  const epoch = ++generation; loading.value = true; error.value = ''; rows.value = []
  try { const result = await props.adapter.listApplications({ ...query }); if (active && epoch === generation) { rows.value = result.items; total.value = result.total } }
  catch (value) { if (active && epoch === generation) failed(value) }
  finally { if (active && epoch === generation) loading.value = false }
}
function filter() { query.page = 1; void load() }
function pageChanged(page: number) { query.page = page; void load() }
function edit(row: MembershipApplication) { selected.value = { ...row }; decision.value = 'approve'; role.value = ''; reason.value = ''; formError.value = ''; conflict.value = false; open.value = true }
async function refreshConflict() { open.value = false; selected.value = undefined; await load() }
async function save() {
  if (saving.value || conflict.value || !selected.value) return
  if (decision.value === 'approve' && !Object.hasOwn(props.roles, role.value)) { formError.value = '请选择本业务的有效角色'; return }
  if (decision.value === 'reject' && !reason.value.trim()) { formError.value = '请填写拒绝原因'; return }
  saving.value = true; formError.value = ''
  const current = { ...selected.value }, input = { decision: decision.value, version: selected.value.version, ...(decision.value === 'approve' ? { role: role.value } : { reason: reason.value.trim() }) }
  try {
    confirming = true
    try { await ElMessageBox.confirm(input.decision === 'approve' ? `确认批准「${current.name}」加入${props.businessName}业务，并授予${props.roles[role.value]}角色？` : `确认拒绝「${current.name}」的${props.businessName}业务申请？`, '确认审批', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }) } catch { return }
    finally { confirming = false }
    if (!active) return
    await props.adapter.decideApplication(current.id, input)
    if (!active) return
    open.value = false; selected.value = undefined; emit('changed'); ElMessage.success('申请审批已完成'); await load()
  } catch (value) {
    if (!active) return
    if ([401, 403].includes(Number(statusOf(value)))) failed(value)
    else { formError.value = statusOf(value) === 409 ? '申请状态或版本已变化，请刷新最新申请后重新审批' : value instanceof Error ? value.message : '审批失败，请重试'; conflict.value = statusOf(value) === 409 }
  } finally { saving.value = false }
}
const columns = [{ prop: 'name', label: '申请人', minWidth: 110 }, { prop: 'status', label: '申请状态', minWidth: 110, useSlot: true }, { prop: 'createdAt', label: '申请时间', minWidth: 180, useSlot: true }, { prop: 'reason', label: '审批意见', minWidth: 180, useSlot: true }, { prop: 'action', label: '操作', width: 110, useSlot: true }]
onMounted(load)
onUnmounted(() => { active = false; ++generation; if (confirming) ElMessageBox.close() })
</script>
