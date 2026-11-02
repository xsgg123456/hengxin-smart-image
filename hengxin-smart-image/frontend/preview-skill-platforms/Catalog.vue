<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h2>海外 Skill 目录</h2><p>按平台管理 Skill；AI 设计工作台仅显示当前任务平台下已开启的 Skill。</p></div><ElButton :loading="loading" @click="refresh">刷新 Skill</ElButton></div>
    <ElTabs v-model="group" class="platform-tabs" @tab-change="selected = []">
      <ElTabPane :label="`全部 (${skills.length})`" name="all" />
      <ElTabPane v-for="p in platforms" :key="p.value" :label="`${p.value} (${count(p.value)})`" :name="p.value" />
      <ElTabPane :label="`未分组 (${count('none')})`" name="none" />
    </ElTabs>
    <div class="catalog-toolbar">
      <div class="catalog-filters"><ElInput v-model="search" class="hx-search" aria-label="搜索 Skill" placeholder="搜索名称或描述" clearable /><ElSelect v-model="status" aria-label="筛选启用状态" style="width:140px"><ElOption label="全部状态" value="all" /><ElOption label="已开启" value="enabled" /><ElOption label="已关闭" value="disabled" /></ElSelect></div>
      <div class="studio-actions"><ElButton :disabled="!selected.length" @click="edit(selected)">批量设置平台<span v-if="selected.length">（{{ selected.length }}）</span></ElButton><ElButton v-if="isPlatform" type="primary" @click="addOpen = true; additions = []; addSearch = ''">添加 Skill 到此平台</ElButton></div>
    </div>
    <div class="catalog-context"><span>{{ group === 'all' ? '全部已安装 Skill' : group === 'none' ? '未分配平台的 Skill，不出现在工作台选项中' : `${group} 平台 · 同一个 Skill 可同时属于多个平台` }} · {{ rows.length }} 项</span><ElButton v-if="isPlatform" text size="small" @click="taskPlatform = group; $emit('studio')">查看工作台可选项（{{ skills.filter(s => s.enabled && s.platforms.includes(group)).length }}） →</ElButton></div>
    <ArtTable :data="rows" :columns="columns" :loading="loading" :cell-style="{ verticalAlign: 'top' }" height="auto" empty-height="240px" :show-table-header="false" :show-pagination="false" :empty-text="search || status !== 'all' ? '暂无匹配的 Skill，请调整筛选' : group === 'none' ? '所有 Skill 均已分配平台' : isPlatform ? '此平台还没有 Skill，点击上方按钮添加' : '暂无已安装 Skill'" @selection-change="selectRows">
      <template #displayName="{ row }"><span class="skill-text">{{ row.displayName }}</span></template>
      <template #description="{ row }"><span class="skill-text">{{ row.description }}</span></template>
      <template #platforms="{ row }"><div class="platform-tags"><ElTag v-for="p in row.platforms" :key="p" size="small" effect="plain">{{ p }}</ElTag><span v-if="!row.platforms.length" class="hx-muted">未分组</span></div></template>
      <template #availability="{ row }"><div class="availability"><ElTag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '已开启' : '已关闭' }}</ElTag><ElButton size="small" @click="row.enabled = !row.enabled">{{ row.enabled ? '关闭' : '开启' }}</ElButton></div></template>
      <template #actions="{ row }"><div class="availability"><ElButton text size="small" @click="edit([row.id])">编辑平台</ElButton><ElButton v-if="isPlatform" text type="danger" size="small" @click="remove(row)">移出平台</ElButton></div></template>
    </ArtTable>
    <p class="catalog-foot">平台分组沿用提交图需中的目标平台。开关对该 Skill 的所有平台生效；移出平台保留 Skill 文件与历史任务。</p>
  </ElCard>
  <ElDialog v-model="editOpen" :title="editing.length > 1 ? `批量设置平台 · ${editing.length} 个 Skill` : '编辑适用平台'" width="min(620px,94vw)" append-to-body>
    <p class="dialog-skill">{{ editing.length === 1 ? skills.find(s => s.id === editing[0])?.displayName : '保存后，所选 Skill 将统一使用下面的平台归属。' }}</p>
    <p class="dialog-note">可同时选择多个平台。未选择平台时，Skill 归入“未分组”，不出现在工作台。</p>
    <ElCheckboxGroup v-model="draftPlatforms" class="platform-checks"><ElCheckbox v-for="p in platforms" :key="p.value" :value="p.value" border>{{ p.label }}</ElCheckbox></ElCheckboxGroup>
    <div class="dialog-link-row"><ElButton text size="small" @click="draftPlatforms = platforms.map(p => p.value)">选择全部平台</ElButton><ElButton text size="small" @click="draftPlatforms = []">清空选择</ElButton></div>
    <p class="dialog-note">只调整平台归属，不修改 Skill 内容、字体和执行逻辑。</p>
    <template #footer><ElButton @click="editOpen = false">取消</ElButton><ElButton type="primary" @click="save">保存平台设置</ElButton></template>
  </ElDialog>
  <ElDialog v-model="addOpen" :title="`添加 Skill 到 ${group}`" width="min(700px,94vw)" append-to-body>
    <p class="dialog-note">选择已安装的 Skill 加入当前平台，已有的其他平台归属保留。</p><ElInput v-model="addSearch" placeholder="搜索要添加的 Skill" aria-label="搜索待添加 Skill" clearable />
    <ElCheckboxGroup v-model="additions" class="add-list"><ElCheckbox v-for="s in candidates" :key="s.id" :value="s.id"><span>{{ s.displayName }}</span><small>{{ s.platforms.length ? `已属于：${s.platforms.join('、')}` : '未分组' }} · {{ s.enabled ? '已开启' : '已关闭' }}</small></ElCheckbox></ElCheckboxGroup>
    <ElEmpty v-if="!candidates.length" description="暂无可添加的 Skill" :image-size="60" />
    <template #footer><ElButton @click="addOpen = false">取消</ElButton><ElButton type="primary" :disabled="!additions.length" @click="add">添加到 {{ group }}（{{ additions.length }}）</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { skills, platforms, taskPlatform, type PreviewSkill } from './state'
defineEmits<{ studio: [] }>()
const group = ref('all'), search = ref(''), status = ref('all'), selected = ref<string[]>([]), loading = ref(false)
const editOpen = ref(false), editing = ref<string[]>([]), draftPlatforms = ref<string[]>([])
const addOpen = ref(false), additions = ref<string[]>([]), addSearch = ref('')
const isPlatform = computed(() => platforms.some(p => p.value === group.value))
const matches = (s: PreviewSkill, q: string) => `${s.displayName} ${s.description}`.toLowerCase().includes(q.trim().toLowerCase())
const count = (p: string) => skills.filter(s => p === 'none' ? !s.platforms.length : s.platforms.includes(p)).length
const rows = computed(() => skills.filter(s => (group.value === 'all' || (group.value === 'none' ? !s.platforms.length : s.platforms.includes(group.value))) && matches(s, search.value) && (status.value === 'all' || s.enabled === (status.value === 'enabled'))))
const candidates = computed(() => skills.filter(s => !s.platforms.includes(group.value) && matches(s, addSearch.value)))
const columns = [ { type: 'selection' as const, width: 44 }, { prop: 'displayName', label: '名称', minWidth: 235, useSlot: true }, { prop: 'description', label: '描述', minWidth: 350, useSlot: true }, { prop: 'platforms', label: '适用平台', width: 190, useSlot: true }, { prop: 'availability', label: '状态', width: 88, useSlot: true }, { prop: 'actions', label: '操作', width: 100, useSlot: true } ]
function selectRows(rows: PreviewSkill[]) { selected.value = rows.map(s => s.id) }
function edit(ids: string[]) { editing.value = [...ids]; draftPlatforms.value = ids.length === 1 ? [...skills.find(s => s.id === ids[0])!.platforms] : []; editOpen.value = true }
function save() { for (const s of skills) if (editing.value.includes(s.id)) s.platforms = [...draftPlatforms.value]; editOpen.value = false; ElMessage.success('平台归属已更新，工作台预览同步生效') }
function add() { for (const s of skills) if (additions.value.includes(s.id) && !s.platforms.includes(group.value)) s.platforms.push(group.value); addOpen.value = false; ElMessage.success(`已添加 ${additions.value.length} 个 Skill 到 ${group.value}`) }
async function remove(s: PreviewSkill) { try { await ElMessageBox.confirm(`将「${s.displayName}」移出 ${group.value}？保留其他平台归属、Skill 文件与历史任务。`, '移出当前平台', { type: 'warning', confirmButtonText: '确认移出', cancelButtonText: '取消' }); s.platforms = s.platforms.filter(p => p !== group.value); ElMessage.success('已移出当前平台') } catch { /* cancelled */ } }
let timer: ReturnType<typeof setTimeout> | undefined
function refresh() { loading.value = true; timer = setTimeout(() => { loading.value = false; ElMessage.success('预览目录已刷新，当前模拟设置保留') }, 450) }
onUnmounted(() => { if (timer) clearTimeout(timer) })
</script>
<style scoped>
.hx-admin-section-head { flex-wrap:wrap; gap:12px; }
.platform-tabs { margin:8px 0 16px; }
.catalog-toolbar,.catalog-filters,.catalog-context { display:flex; flex-wrap:wrap; align-items:center; gap:12px; }
.catalog-filters { flex:1; min-width:280px; }
.catalog-filters .hx-search { width:255px; }
.catalog-toolbar,.catalog-context { justify-content:space-between; }
.catalog-context { margin:14px 0; min-height:28px; font-size:12px; color:var(--art-gray-500); }
.skill-text { display:block; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6; }
.availability { display:flex; flex-direction:column; align-items:flex-start; gap:8px; }
.availability .el-button { margin-left:0; }
.platform-tags { display:flex; flex-wrap:wrap; gap:6px; }
.catalog-foot,.dialog-note { font-size:12px; color:var(--art-gray-500); line-height:1.8; }
.catalog-foot { margin-top:18px; }
.dialog-skill { font-weight:600; line-height:1.7; margin:0 0 12px; }
.platform-checks { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:20px; }
.platform-checks .el-checkbox { margin:0; height:46px; width:100%; }
.dialog-link-row { display:flex; gap:12px; margin:10px 0 20px; }
.add-list { display:flex; flex-direction:column; max-height:360px; overflow:auto; margin-top:14px; }
.add-list .el-checkbox { height:auto; min-height:62px; padding:12px 0; margin:0; border-bottom:1px solid var(--default-border); }
.add-list :deep(.el-checkbox__label) { white-space:normal; overflow-wrap:anywhere; }
.add-list small { display:block; margin-top:6px; color:var(--art-gray-500); }
@media(max-width:640px) { .platform-checks { grid-template-columns:1fr; } }
</style>
