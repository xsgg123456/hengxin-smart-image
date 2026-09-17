<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">SKILL VERSIONS</span><h1>Skill 管理</h1><p>登记后人工部署，检查通过再显式启用；历史任务保持固定引用。</p></div><ElButton type="primary" :disabled="registering" @click="openRegistration()">登记本地 Skill</ElButton></div><AdminPreview />
    <ElCard class="art-card hx-section"><div class="hx-filter"><span class="hx-muted">仅超级管理员维护 · 单 Linux Worker</span><ElButton :loading="loading" @click="load">刷新版本</ElButton></div><ElAlert v-if="error || actionError" :title="error || actionError" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
      <ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="groups" :columns="[]" row-key="key" :expand-row-keys="expanded" @expand-change="onExpand" :loading="loading" :show-pagination="false" empty-text="暂无 Skill，请登记本地版本">
        <ElTableColumn type="expand" width="48">
          <template #default="{ row: group }">
            <div class="hx-section">
              <p class="hx-muted">{{ group.name }} · 全部版本（{{ group.versions.length }}）</p>
              <ArtTable height="auto" :show-table-header="false" :data="group.versions" :columns="columns" :show-pagination="false" row-key="id">
        <template #name="{ row }"><strong>{{ row.version }}{{row.isDefault?' · 模块默认':''}}</strong><p class="hx-muted">{{ row.sourceType==='local'?'本地部署':'历史 ZIP' }} · {{ row.referenced ? '已被模板或任务引用' : '尚无引用' }}</p></template>
        <template #status="{ row }"><ElTag :type="['failed','invalid'].includes(row.status)?'danger':row.status==='available'?'success':'info'">{{ statuses[row.status as keyof typeof statuses] }}</ElTag><p v-if="row.error" class="hx-muted">{{ row.error }}</p></template>
        <template #details="{ row }"><ElButton text type="primary" @click="selected=row;detailOpen=true">校验与部署记录</ElButton></template>
        <template #action="{ row }">
          <div><ElButton v-if="row.sourceType==='local'" text type="primary" :disabled="!!busy || row.status==='checking'" :loading="busy===row.id" @click="checkDeployment(row)">检查部署</ElButton><ElButton v-if="['verified','disabled'].includes(row.status)" text type="primary" :disabled="!!busy" @click="publish(row)">启用</ElButton><ElButton v-if="row.status==='available'" text type="danger" :disabled="!!busy" @click="disable(row)">停用</ElButton></div>
          <ElButton v-if="row.sourceType==='local'" text type="danger" :disabled="!!busy || row.referenced || row.isDefault || row.status==='checking'" @click="remove(row)">移除登记</ElButton>
        </template>
              </ArtTable>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Skill" min-width="240"><template #default="{ row }"><strong>{{ row.name }}</strong><p class="hx-muted">{{ labels[row.mode as Mode] }} · {{ row.versions.length }} 个版本</p></template></ElTableColumn>
        <ElTableColumn label="最近登记版本" min-width="160"><template #default="{ row }"><p>{{ row.recent.version }}</p><ElTag :type="['failed','invalid'].includes(row.recent.status)?'danger':row.recent.status==='available'?'success':'info'">{{ statuses[row.recent.status as keyof typeof statuses] }}</ElTag></template></ElTableColumn>
        <ElTableColumn label="模块默认版本" min-width="180"><template #default="{ row }"><ElTag v-if="row.defaultVersion">{{ row.defaultVersion.version }} · 默认</ElTag><span v-else class="hx-muted">未设为模块默认</span></template></ElTableColumn>
        <ElTableColumn label="操作" min-width="220"><template #default="{ row }"><ElButton text type="primary" :aria-expanded="expanded.includes(row.key)" @click="toggleGroup(row)">{{ expanded.includes(row.key) ? '收起版本' : '查看版本' }}</ElButton><ElButton text type="primary" :disabled="!!busy || registering" @click="openRegistration(row.recent)">更新版本</ElButton></template></ElTableColumn>
      </ArtTable><p class="hx-footnote">展开查看版本来源及检查、启停操作。登记不代表已部署或默认使用；模板和任务保持固定版本。</p>
    </ElCard>
    <SkillDefaults :skills="data || []" @saved="load" />
    <ElDialog v-model="registrationOpen" :title="updateFrom ? '更新 Skill 版本' : '登记 Skill 版本'" width="520px" :close-on-click-modal="!registering" :show-close="!registering" :close-on-press-escape="!registering">
      <ElAlert type="info" :closable="false" class="hx-gap" title="先登记，再人工部署并检查">
        <p v-if="updateFrom">{{ updateFrom.name }} · 当前所选版本 {{ updateFrom.version }}。请填写新版本号，原版本及默认绑定保持不变。</p>
        <p v-if="updateFrom?.sourceType==='zip'">历史 ZIP 名称可替换为合法 Skill 标识；使用不同标识会新建分组，旧版本及其绑定保留。</p>
        <p>管理员将版本部署至配置的发布目录，按“标识/版本/SKILL.md”组织。检查通过后仍需手动启用。</p>
      </ElAlert>
      <ElForm label-position="top" :disabled="registering">
        <ElFormItem label="Skill 标识"><ElInput v-model="name" :disabled="updateFrom?.sourceType==='local'" maxlength="100" placeholder="例如 wallpaper-replace" aria-label="Skill 标识" /></ElFormItem>
        <ElFormItem label="处理类型"><ElSelect v-model="mode" :disabled="!!updateFrom" aria-label="Skill 类型"><ElOption v-for="(label,key) in labels" :key="key" :value="key" :label="label" /></ElSelect></ElFormItem>
        <ElFormItem label="版本号"><ElInput v-model="version" placeholder="例如 1.1.0" maxlength="100" aria-label="Skill 版本号" /></ElFormItem>
        <ElFormItem label="说明（可选）"><ElInput v-model="description" type="textarea" maxlength="2000" :rows="3" aria-label="Skill 说明" /></ElFormItem>
      </ElForm>
      <p class="hx-footnote">标识使用字母、数字、连字符或下划线，不填写服务器路径。{{isMockMode?'当前模拟登记和检查，不验证服务器文件。':''}}</p>
      <ElAlert v-if="registrationError" :title="registrationError" type="error" :closable="false" />
      <template #footer><ElButton :disabled="registering" @click="registrationOpen=false">取消</ElButton><ElButton type="primary" :loading="registering" :disabled="!name.trim() || !version.trim()" @click="register">登记版本</ElButton></template>
    </ElDialog>
    <ElDialog v-model="detailOpen" title="版本记录" width="560px"><template v-if="selected"><p>来源：{{ selected.sourceType==='local'?'本地部署':'历史 ZIP' }}</p><p v-if="selected.description" style="overflow-wrap:anywhere">说明：{{selected.description}}</p><p>版本：{{ selected.version }} · {{ selected.referenced?'已被模板或任务引用':'尚无引用' }}</p><p style="overflow-wrap:anywhere">内容校验值：{{ selected.checksum || '尚未记录' }}</p><p>节点：{{selected.node||'尚未检查'}}</p><p>最近校验 / 历史安装时间：{{selected.installedAt?new Date(selected.installedAt).toLocaleString('zh-CN'):'尚未记录'}}</p><p>最近变更：{{new Date(selected.updatedAt).toLocaleString('zh-CN')}}</p><ElAlert v-if="selected.error" :title="selected.error" type="error" :closable="false" /></template></ElDialog>
  </div>
</template>
<script setup lang="ts">
import { isSkillVersion } from '@/utils/skill-version'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listManagedSkills, registerSkill, checkSkill, removeSkill, setSkillStatus } from '@/api/management'
import { isMockMode } from '@/api/hengxin/client'
import type { Mode } from '@/types/hengxin'
import type { ManagedSkill } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { labels } from '../model'
import AdminPreview from './AdminPreview.vue'
import SkillDefaults from './SkillDefaults.vue'
import { useAdminQuery } from './use-admin-query'
import { groupSkills, type SkillGroup } from './skill-groups'
const {data,loading,error,load}=useAdminQuery(listManagedSkills)
const groups=computed(()=>groupSkills(data.value||[])),expanded=ref<string[]>([])
function onExpand(_row:SkillGroup,rows:SkillGroup[]){expanded.value=rows.map(row=>row.key)}
function toggleGroup(row:SkillGroup){expanded.value=expanded.value.includes(row.key)?expanded.value.filter(key=>key!==row.key):[...expanded.value,row.key]}
const busy=ref(''),actionError=ref(''),registrationOpen=ref(false),registering=ref(false),registrationError=ref(''),name=ref(''),description=ref(''),version=ref(''),mode=ref<Mode>('wallpaper'),selected=ref<ManagedSkill>(),detailOpen=ref(false)
const updateFrom=ref<ManagedSkill>()
function openRegistration(row?:ManagedSkill){
  if(registering.value)return
  updateFrom.value=row;mode.value=row?.mode??'wallpaper';version.value=''
  name.value=row?.name??'';description.value='';registrationError.value='';registrationOpen.value=true
}
const statuses={pending:'待部署',checking:'检查中',verified:'已验证未启用',invalid:'检查失败',uploaded:'已上传',installing:'安装中',available:'可用',disabled:'已停用',failed:'安装失败'}
let timer:ReturnType<typeof setTimeout>|undefined
watch(data,rows=>{clearTimeout(timer);if(rows?.some(row=>['installing','checking'].includes(row.status)))timer=setTimeout(load,1000)});onBeforeUnmount(()=>clearTimeout(timer))
async function register(){
  if(registering.value)return
  registrationError.value=''
  if(!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/.test(name.value.trim()) || !isSkillVersion(version.value.trim())){registrationError.value='请填写合法标识与语义版本（例如 1.1.0）';return}
  registering.value=true
  try{await registerSkill({name:name.value.trim(),mode:mode.value,version:version.value.trim(),description:description.value.trim()});registrationOpen.value=false;ElMessage.success('版本已登记，请部署后检查');await load()}
  catch(e){registrationError.value=e instanceof Error?e.message:'登记失败，请重试'}finally{registering.value=false}
}
async function action(row:ManagedSkill,run:()=>Promise<ManagedSkill>){if(busy.value)return;busy.value=row.id;actionError.value='';try{const accepted=await run();if(data.value)data.value=data.value.map(item=>item.id===accepted.id?accepted:item);await load()}catch(e){actionError.value=e instanceof Error?e.message:'操作失败，请重试'}finally{busy.value=''}}
async function checkDeployment(row:ManagedSkill){
  if(row.status==='available'){try{await ElMessageBox.confirm('重新检查将暂停此版本的新任务使用；通过后需重新启用。','重新检查部署',{type:'warning',confirmButtonText:'确认检查',cancelButtonText:'取消'})}catch{return}}
  await action(row,()=>checkSkill(row.id))
}
async function remove(row:ManagedSkill){
  try{await ElMessageBox.confirm(`移除 ${row.name} ${row.version} 的登记？服务器文件不会删除。`,'移除登记',{type:'warning',confirmButtonText:'确认移除',cancelButtonText:'取消'})}catch{return}
  if(busy.value)return
  busy.value=row.id;actionError.value=''
  try{await removeSkill(row.id);if(data.value)data.value=data.value.filter(item=>item.id!==row.id);await load();ElMessage.success('登记已移除，服务器文件保留')}
  catch(e){actionError.value=e instanceof Error?e.message:'移除失败，请重试'}finally{busy.value=''}
}
function publish(row:ManagedSkill){void action(row,()=>setSkillStatus(row.id,'available'))}
async function disable(row:ManagedSkill){try{await ElMessageBox.confirm('停用后新任务不能选择此版本，历史任务的固定引用保留。','停用 Skill',{type:'warning',confirmButtonText:'确认停用',cancelButtonText:'取消'})}catch{return}await action(row,()=>setSkillStatus(row.id,'disabled'))}
const columns=[{prop:'name',label:'版本 / 引用',minWidth:220,useSlot:true},{prop:'status',label:'状态',minWidth:170,useSlot:true},{prop:'details',label:'版本信息',minWidth:150,useSlot:true},{prop:'action',label:'操作',minWidth:220,useSlot:true}]
</script>
