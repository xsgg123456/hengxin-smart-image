<template>
  <div class="hx-page">
    <div class="hx-heading"><div><h1>Skill 管理</h1><p>在服务器维护 Skill 目录后同步，描述自动读取。新任务使用最近同步成功的内容。</p></div><ElButton type="primary" :loading="syncing" :disabled="loading || !!busy || !!error" @click="synchronize">同步 Skill</ElButton></div>
    <AdminPreview />
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重新加载</ElButton></ElAlert>
    <ElAlert v-if="actionError || syncError" :title="actionError || syncError" type="error" :closable="false" />
    <ElAlert v-if="syncing" title="正在同步 Skill，请稍候…" type="info" :closable="false" />
    <ElCard class="art-card hx-section">
      <ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="data || []" :columns="columns" :loading="loading" :show-pagination="false" empty-text="暂无 Skill，请先维护服务器目录，再点击同步 Skill">
        <template #name="{ row }"><strong style="overflow-wrap:anywhere">{{ row.name }}</strong><ElTag v-if="row.isDefault" size="small" class="hx-gap">默认</ElTag></template>
        <template #description="{ row }"><p class="skill-description" :class="{ collapsed: !expanded.includes(row.id) }">{{ row.description || '未提供描述' }}</p><ElButton v-if="row.description" text type="primary" size="small" @click="toggleDescription(row.id)">{{ expanded.includes(row.id) ? '收起描述' : '展开全文' }}</ElButton></template>
        <template #mode="{ row }"><span v-if="row.mode">{{ labels[row.mode as Mode] }}</span><ElSelect v-else placeholder="需选类型" aria-label="选择 Skill 处理类型" :disabled="blocked" @change="(mode: Mode) => chooseMode(row, mode)"><ElOption v-for="(label, mode) in labels" :key="mode" :value="mode" :label="label" /></ElSelect></template>
        <template #status="{ row }"><ElTag :type="row.status === 'available' ? 'success' : ['invalid','needs_type'].includes(row.status) ? 'danger' : 'info'">{{ statuses[row.status as CatalogSkill['status']] }}</ElTag><p v-if="row.error" class="hx-muted" style="overflow-wrap:anywhere">{{ row.error }}</p></template>
        <template #action="{ row }">
          <ElButton v-if="row.status === 'available' || row.status === 'disabled'" text type="primary" :disabled="blocked" @click="toggleStatus(row)">{{ row.status === 'disabled' ? '启用' : '停用' }}</ElButton>
          <ElButton text type="danger" :disabled="blocked || row.referenced || row.isDefault" @click="remove(row)">移除</ElButton>
          <p v-if="row.referenced || row.isDefault" class="hx-muted">解除模板 / 默认绑定后可移除</p>
        </template>
      </ArtTable>
    </ElCard>
    <SkillDefaults v-if="data && !error" :skills="data" :disabled="blocked" @saved="load" />
    <p class="hx-footnote">移除只撤销平台登记，服务器文件保留；再次同步仍会发现该目录。已提交任务保留原内容。{{ isMockMode ? '当前为模拟同步，不读取真实服务器目录。' : '' }}</p>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listManagedCatalog, getSkillSync, syncSkillCatalog, setCatalogMode, setCatalogStatus, removeCatalogSkill } from '@/api/management'
import { isMockMode } from '@/api/hengxin/client'
import type { CatalogSkill } from '@/types/management'
import type { Mode } from '@/types/hengxin'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { labels } from '../model'
import AdminPreview from './AdminPreview.vue'
import SkillDefaults from './SkillDefaults.vue'
import { useAdminQuery } from './use-admin-query'
const syncing = ref(false), syncError = ref(''), actionError = ref(''), busy = ref(false), expanded = ref<string[]>([])
let alive = true, timer: ReturnType<typeof setTimeout> | undefined
const { data, loading, error, load } = useAdminQuery(async () => {
  const [rows, job] = await Promise.all([listManagedCatalog(), getSkillSync()])
  if (alive) {
    syncing.value = ['queued', 'running'].includes(job.status); syncError.value = job.error || ''
    clearTimeout(timer); if (syncing.value) timer = setTimeout(load, 1200)
  }
  return rows
})
onBeforeUnmount(() => { alive = false; clearTimeout(timer) })
const blocked = computed(() => loading.value || busy.value || syncing.value || !!error.value)
const statuses = { available: '可用', disabled: '停用', invalid: '异常', needs_type: '需选类型', syncing: '同步中' }
function toggleDescription(id: string) { expanded.value = expanded.value.includes(id) ? expanded.value.filter(value => value !== id) : [...expanded.value, id] }
async function action(run: () => Promise<unknown>) {
  if (blocked.value) return
  busy.value = true; actionError.value = ''
  try { await run(); if (alive) await load() }
  catch (e) { if (alive) actionError.value = e instanceof Error ? e.message : '操作失败，请重试' }
  finally { if (alive) busy.value = false }
}
async function synchronize() { await action(async () => { await syncSkillCatalog(); syncing.value = true; ElMessage.success('同步已受理') }) }
async function chooseMode(row: CatalogSkill, mode: Mode) { await action(() => setCatalogMode(row.id, mode)) }
async function toggleStatus(row: CatalogSkill) {
  if (row.status === 'available') {
    try { await ElMessageBox.confirm('停用后新任务不可使用此 Skill，已提交任务继续使用原内容。', '停用 Skill', { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' }) } catch { return }
  }
  await action(() => setCatalogStatus(row.id, row.status === 'disabled' ? 'available' : 'disabled'))
}
async function remove(row: CatalogSkill) {
  try { await ElMessageBox.confirm(`移除 ${row.name} 的平台登记？服务器文件不会删除。`, '移除 Skill', { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' }) } catch { return }
  await action(() => removeCatalogSkill(row.id))
}
const columns = [{ prop: 'name', label: 'Skill', minWidth: 180, useSlot: true }, { prop: 'description', label: '描述', minWidth: 280, useSlot: true }, { prop: 'mode', label: '处理类型', minWidth: 140, useSlot: true }, { prop: 'status', label: '状态', minWidth: 150, useSlot: true }, { prop: 'action', label: '操作', minWidth: 200, useSlot: true }]
</script>
<style scoped>
.skill-description { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
.skill-description.collapsed { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
</style>
