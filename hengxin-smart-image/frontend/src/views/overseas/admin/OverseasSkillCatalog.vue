<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h2>海外 Skill 目录</h2><p>{{ managed ? '按平台管理 Skill；AI 设计工作台仅显示当前任务平台下已开启的 Skill。' : '查看已安装 Skill 的名称与描述。' }}</p><p v-if="managed && !loading && !error && !canToggle">仅指定账号可调整 Skill 开关。</p></div><ElButton :loading="loading" :disabled="!!savingId || !!dialog" @click="$emit('refresh')">刷新 Skill</ElButton></div>
    <ElTabs v-if="managed" v-model="group" class="platform-tabs">
      <ElTabPane :label="`全部 (${skills.length})`" name="all" />
      <ElTabPane v-for="p in platforms" :key="p.value" :label="`${p.value} (${count(p.value)})`" :name="p.value" />
      <ElTabPane :label="`未分组 (${count('none')})`" name="none" />
    </ElTabs>
    <div class="catalog-toolbar">
      <div class="catalog-filters"><ElInput v-model="search" class="hx-search" aria-label="搜索 Skill" placeholder="搜索名称或描述" clearable /><ElSelect v-if="managed" v-model="status" aria-label="筛选启用状态" style="width:140px"><ElOption label="全部状态" value="all" /><ElOption label="已开启" value="enabled" /><ElOption label="已关闭" value="disabled" /></ElSelect></div>
      <div v-if="canManagePlatforms" class="catalog-actions"><ElButton :disabled="!selected.length || blocked" @click="edit(selected)">批量设置平台<span v-if="selected.length">（{{ selected.length }}）</span></ElButton><ElButton v-if="isPlatform" type="primary" :disabled="blocked" @click="openAdd">添加 Skill 到此平台</ElButton></div>
    </div>
    <div v-if="managed" class="catalog-context"><span>{{ group === 'all' ? '全部已安装 Skill' : group === 'none' ? '未分配平台的 Skill，不出现在工作台选项中' : `${group} 平台 · 同一个 Skill 可同时属于多个平台` }} · {{ rows.length }} 项</span><span v-if="hiddenSelected">另有 {{ hiddenSelected }} 项已选 Skill 被筛选隐藏，批量设置仍会包含它们</span><ElButton v-if="selected.length" text size="small" :disabled="blocked" @click="clearSelection">清空已选</ElButton></div>
    <p v-if="loading" role="status">正在加载 Skill 目录…</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <ElAlert v-if="notice" :title="notice" type="info" :closable="false" class="hx-gap" />
    <ArtTable v-if="!error" ref="table" row-key="id" :data="rows" :columns="columns" :cell-style="{ verticalAlign: 'top' }" :loading="loading" height="auto" empty-height="240px" :show-table-header="false" :show-pagination="false" :empty-text="emptyText" @selection-change="selectRows">
      <template #displayName="{ row }"><span class="skill-text">{{ row.displayName }}</span></template>
      <template #description="{ row }"><span class="skill-text">{{ row.description || '暂无描述' }}</span></template>
      <template #platforms="{ row }"><div class="platform-tags"><ElTag v-for="p in row.platforms" :key="p" size="small" effect="plain">{{ p }}</ElTag><span v-if="!row.platforms?.length" class="hx-muted">未分组</span></div></template>
      <template #availability="{ row }"><div class="skill-availability"><ElTag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '已开启' : '已关闭' }}</ElTag><ElButton v-if="canToggle" size="small" :aria-label="`${row.enabled ? '关闭' : '开启'} ${row.displayName}`" :loading="savingId === row.id" :disabled="blocked || !!dialog" @click="$emit('toggle', row.id)">{{ row.enabled ? '关闭' : '开启' }}</ElButton></div></template>
      <template #actions="{ row }"><div v-if="canManagePlatforms" class="skill-availability"><ElButton text size="small" :disabled="blocked" @click="edit([row.id])">编辑平台</ElButton><ElButton v-if="isPlatform" text type="danger" size="small" :disabled="blocked" @click="remove(row)">移出平台</ElButton></div></template>
    </ArtTable>
    <p v-if="managed" class="catalog-foot">平台分组沿用提交图需中的目标平台。开关对该 Skill 的所有平台生效；移出平台保留 Skill 文件与历史任务。</p>
  </ElCard>
  <OverseasSkillPlatformsDialog v-if="dialog && savePlatforms" :skills="managedSkills" :ids="editing" :mode="dialog" :platform="dialogPlatform" :can-manage="!!canManagePlatforms" :save-platforms="savePlatforms" :refresh-platforms="refreshPlatforms" :error="platformError || ''" @close="dialog = undefined" />
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import type { Skill, ManagedSkill, SkillPlatformUpdate } from '@/api/overseas/management'
import { OVERSEAS_PLATFORMS as platforms } from '../platforms'
import OverseasSkillPlatformsDialog from './OverseasSkillPlatformsDialog.vue'
const props = defineProps<{ skills: Skill[]; loading?: boolean; error?: string; managed?: boolean; canToggle?: boolean; savingId?: string; notice?: string; canManagePlatforms?: boolean; platformError?: string; refreshPlatforms?: () => Promise<void>; savePlatforms?: (items: SkillPlatformUpdate[]) => Promise<boolean> }>()
const emit = defineEmits<{ refresh: []; toggle: [id: string]; edit: [] }>()
const group = ref('all'), search = ref(''), status = ref('all'), selected = ref<string[]>([])
const dialog = ref<'edit' | 'add'>(), editing = ref<string[]>([]), dialogPlatform = ref('')
const table = ref<InstanceType<typeof ArtTable>>()
const managedSkills = computed(() => props.managed ? props.skills as ManagedSkill[] : [])
const isPlatform = computed(() => platforms.some(p => p.value === group.value))
const blocked = computed(() => !!props.loading || !!props.savingId || !!props.error)
const belongs = (s: Skill, p: string) => { const values = (s as ManagedSkill).platforms || []; return p === 'all' || (p === 'none' ? !values.length : values.includes(p)) }
const count = (p: string) => props.skills.filter(s => belongs(s, p)).length
const rows = computed(() => props.skills.filter(s => (!props.managed || belongs(s, group.value)) && [s.displayName, s.name, s.description].some(v => v.toLowerCase().includes(search.value.trim().toLowerCase())) && (!props.managed || status.value === 'all' || (s as ManagedSkill).enabled === (status.value === 'enabled'))))
const hiddenSelected = computed(() => selected.value.filter(id => !rows.value.some(s => s.id === id)).length)
const emptyText = computed(() => search.value.trim() || status.value !== 'all' ? '暂无匹配的 Skill，请调整筛选' : group.value === 'none' ? '所有 Skill 均已分配平台' : isPlatform.value ? '此平台还没有 Skill' : '暂无已安装 Skill')
const columns = computed(() => [
  ...(props.canManagePlatforms ? [{ type: 'selection' as const, width: 44, reserveSelection: true, selectable: () => !blocked.value }] : []),
  { prop: 'displayName', label: '名称', minWidth: 200, useSlot: true }, { prop: 'description', label: '描述', minWidth: 300, useSlot: true },
  ...(props.managed ? [{ prop: 'platforms', label: '适用平台', width: 190, useSlot: true }, { prop: 'availability', label: '状态', width: 88, useSlot: true }] : []),
  ...(props.canManagePlatforms ? [{ prop: 'actions', label: '操作', width: 100, useSlot: true }] : [])
])
function selectRows(rows: Skill[]) { selected.value = rows.map(s => s.id).filter(id => props.skills.some(s => s.id === id)) }
function clearSelection() { selected.value = []; table.value?.elTableRef?.clearSelection() }
function edit(ids: string[]) { if (blocked.value || !props.canManagePlatforms) return; emit('edit'); editing.value = [...ids]; dialogPlatform.value = group.value; dialog.value = 'edit' }
function openAdd() { emit('edit'); editing.value = []; dialogPlatform.value = group.value; dialog.value = 'add' }
async function remove(skill: ManagedSkill) {
  if (blocked.value || !props.canManagePlatforms || !props.savePlatforms) return
  const platform = group.value
  try { await ElMessageBox.confirm(`将「${skill.displayName}」移出 ${platform}？保留其他平台归属、Skill 文件与历史任务。`, '移出当前平台', { type: 'warning', confirmButtonText: '确认移出', cancelButtonText: '取消' }) } catch { return }
  await props.savePlatforms([{ id: skill.id, version: skill.version, platforms: skill.platforms.filter(p => p !== platform) }])
}
watch(() => props.skills, () => { selected.value = selected.value.filter(id => props.skills.some(s => s.id === id)) })
</script>
<style scoped>
.hx-admin-section-head { flex-wrap:wrap; gap:12px; }
.hx-admin-section-head > div,.hx-admin-table-card { min-width:0; }
.platform-tabs { margin:8px 0 16px; }
.catalog-toolbar,.catalog-filters,.catalog-context,.catalog-actions { display:flex; flex-wrap:wrap; align-items:center; gap:12px; }
.catalog-filters { flex:1; min-width:260px; }
.catalog-filters .hx-search { width:255px; max-width:100%; }
.catalog-toolbar,.catalog-context { justify-content:space-between; }
.catalog-context { margin:14px 0; min-height:28px; font-size:12px; color:var(--art-gray-500); }
.skill-text { display:block; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6; }
.skill-availability { display:flex; flex-direction:column; align-items:flex-start; gap:8px; }
.skill-availability .el-button,.catalog-actions .el-button { margin-left:0; }
.platform-tags { display:flex; flex-wrap:wrap; gap:6px; }
.catalog-foot { margin-top:18px; font-size:12px; color:var(--art-gray-500); line-height:1.8; }
</style>
