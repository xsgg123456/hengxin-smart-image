<template>
  <section v-if="allowed" class="hx-page domestic-skills">
    <div class="hx-heading"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h1>Skills 管理</h1><p>管理国内工作台的 Skill，用户进入工作台后自动使用绑定能力。</p></div><ElTag>仅超级管理员</ElTag></div>
    <ElCard shadow="never" class="art-card skills-card">
      <ElTabs v-model="tab"><ElTabPane label="Skill 目录" name="catalog" /><ElTabPane label="工作台绑定" name="bindings" /></ElTabs>
      <template v-if="tab === 'catalog'">
        <div class="skills-toolbar"><ElInput v-model="search" aria-label="搜索 Skill" placeholder="搜索名称或描述" clearable /><ElSelect v-model="status" aria-label="Skill 状态"><ElOption label="全部状态" value="all" /><ElOption label="已启用" value="enabled" /><ElOption label="已停用" value="disabled" /></ElSelect><ElButton type="primary" @click="uploadOpen = true">上传 Skill 文件夹</ElButton></div>
        <div class="skills-context"><span>{{ rows.length }} 个 Skill · 示例数据仅用于交互预览</span><span>完整文件夹上传 · 同名 Skill 更新</span></div>
        <ElTable :data="rows" row-key="id" empty-text="暂无匹配 Skill" class="skills-table"><ElTableColumn label="Skill 名称" min-width="200"><template #default="{row}"><strong>{{ row.displayName }}</strong><ElTag v-if="row.demo" size="small" type="info">示例</ElTag></template></ElTableColumn><ElTableColumn prop="description" label="描述" min-width="240" /><ElTableColumn label="绑定工作台" min-width="200"><template #default="{row}"><div v-if="usedBy(row.id).length" class="skills-binding-tags"><ElTag v-for="item in usedBy(row.id)" :key="item.id" size="small" effect="plain">{{ item.title }}</ElTag></div><span v-else class="skills-muted">未绑定</span></template></ElTableColumn><ElTableColumn label="状态" width="130"><template #default="{row}"><ElTag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '已启用' : '已停用' }}</ElTag></template></ElTableColumn><ElTableColumn label="操作" width="246"><template #default="{row}"><div class="skills-row-actions"><ElButton text type="primary" @click="tab = 'bindings'">设置绑定</ElButton><ElButton text :loading="exporting === row.id" :disabled="!!exporting" @click="download(row)">下载 ZIP</ElButton><ElButton text @click="toggle(row)">{{ row.enabled ? '停用' : '启用' }}</ElButton><ElButton text type="danger" @click="remove(row)">删除</ElButton></div></template></ElTableColumn></ElTable>
      </template>
      <template v-else><div class="skills-binding-heading"><div><h2>工作台默认 Skill</h2><p>每个入口绑定一个已启用的 Skill。普通用户无需选择。</p></div><ElButton type="primary" :disabled="!bindingChanged" @click="save">保存绑定</ElButton></div><div class="skills-bindings"><div v-for="workspace in workspaces" :key="workspace.id" class="skills-binding-row"><div><small>{{ workspace.group === 'new' ? '新品生成' : '产品替换' }}</small><strong>{{ workspace.title }}</strong></div><ElSelect v-model="draft[workspace.id]" clearable filterable :aria-label="`${workspace.title}绑定 Skill`" placeholder="未绑定"><ElOption v-for="skill in skills.filter(item => item.enabled)" :key="skill.id" :value="skill.id" :label="`${skill.displayName}${skill.demo ? '（示例）' : ''}`" /></ElSelect><ElTag :type="draft[workspace.id] ? 'success' : 'warning'" size="small">{{ draft[workspace.id] ? '自动使用' : '未配置' }}</ElTag></div></div><p class="skills-muted">保存后对下一次发送生效。未绑定时暂停该工作台的新请求。</p></template>
    </ElCard>
    <p class="skills-muted skills-foot">独立预览 · 数据保存在当前页面内存，刷新恢复示例；未连接服务器 Skill 文件和执行器。</p>
    <SkillUpload v-if="uploadOpen" @close="uploadOpen = false" @saved="uploadOpen = false" />
  </section><section v-else class="hx-page"><h1>仅超级管理员可访问 Skills 管理</h1></section>
</template>
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { skills, bindings, usedBy, canManageSkills, toggleSkill, deleteSkill, saveBindings, type DomesticSkill } from './skills-state'
import { workspaces } from './workspaces'
import SkillUpload from './SkillUpload.vue'
import { exportSkill } from './skills-export'
import './skills.css'
const allowed = computed(canManageSkills), search = ref(''), status = ref('all'), tab = ref('catalog')
const uploadOpen = ref(false), exporting = ref(''), draft = reactive({ ...bindings })
const rows = computed(() => skills.filter(skill => `${skill.displayName} ${skill.name} ${skill.description}`.toLowerCase().includes(search.value.trim().toLowerCase()) && (status.value === 'all' || skill.enabled === (status.value === 'enabled'))))
const bindingChanged = computed(() => workspaces.some(item => draft[item.id] !== bindings[item.id]))
async function download(skill: DomesticSkill) {
  if (exporting.value) return
  exporting.value = skill.id
  try { await exportSkill(skill); ElMessage.success('已发起 ZIP 下载') }
  catch (reason) { if (!(reason instanceof DOMException && reason.name === 'AbortError')) ElMessage.error(reason instanceof Error ? reason.message : '导出失败，请重试') }
  finally { exporting.value = '' }
}
function toggle(skill: DomesticSkill) { try { toggleSkill(skill); ElMessage.success(skill.enabled ? 'Skill 已启用' : 'Skill 已停用') } catch (reason) { ElMessage.warning((reason as Error).message) } }
function save() { try { saveBindings(draft); ElMessage.success('绑定已保存，下一次发送自动使用') } catch (reason) { ElMessage.error((reason as Error).message) } }
async function remove(skill: DomesticSkill) {
  if (usedBy(skill.id).length) { ElMessage.warning('此 Skill 正被工作台使用，请先在「工作台绑定」更换或解除绑定'); return }
  try { await ElMessageBox.confirm(`删除「${skill.displayName}」及其文件包？历史消息和归档不受影响。`, '删除 Skill', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }); deleteSkill(skill); ElMessage.success('Skill 已删除') }
  catch (reason) { if (reason !== 'cancel' && reason !== 'close') ElMessage.error((reason as Error).message) }
}
</script>
