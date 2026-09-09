<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">SKILL VERSIONS</span><h1>Skill 管理</h1><p>上传、安装和发布分别记录；失败保留旧可用版本，历史任务保持固定引用。</p></div><ElButton type="primary" @click="uploadOpen=true">上传 Skill 包</ElButton></div><AdminPreview />
    <ElCard class="art-card hx-section"><div class="hx-filter"><span class="hx-muted">仅超级管理员维护 · 单 Linux Worker</span><ElButton :loading="loading" @click="load">刷新版本</ElButton></div><ElAlert v-if="error || actionError" :title="error || actionError" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
      <ArtTable :data="data || []" :columns="columns" :loading="loading" :show-pagination="false" empty-text="暂无 Skill，请上传版本包">
        <template #name="{ row }"><strong>{{ row.name }}</strong><p class="hx-muted">{{ labels[row.mode as Mode] }} · {{ row.version }}{{row.isDefault?' · 默认':''}}</p></template>
        <template #status="{ row }"><ElTag :type="row.status==='failed'?'danger':row.status==='available'?'success':'info'">{{ statuses[row.status as keyof typeof statuses] }}</ElTag><p v-if="row.error" class="hx-muted">{{ row.error }}</p></template>
        <template #details="{ row }"><ElButton text type="primary" @click="selected=row;detailOpen=true">校验与安装记录</ElButton></template>
        <template #action="{ row }"><ElButton v-if="['uploaded','failed'].includes(row.status)" text type="primary" :disabled="!!busy" :loading="busy===row.id" @click="install(row)">{{row.status==='failed'?'重试安装':'安装版本'}}</ElButton><ElButton v-if="row.status==='disabled'" text type="primary" :disabled="!!busy" @click="publish(row)">设为可用</ElButton><ElButton v-if="row.status==='available'" text type="danger" :disabled="!!busy" @click="disable(row)">停用</ElButton><span v-if="row.status==='installing'" class="hx-muted">安装中…</span></template>
      </ArtTable><p class="hx-footnote">上传成功不代表已安装。被任务引用的版本保留，页面不提供直接删除。</p>
    </ElCard>
    <ElDialog v-model="uploadOpen" title="上传 Skill 版本" width="520px" :close-on-click-modal="!uploading" :show-close="!uploading" :close-on-press-escape="!uploading">
      <ElForm label-position="top" :disabled="uploading"><ElFormItem label="处理类型"><ElSelect v-model="mode" aria-label="Skill 类型"><ElOption v-for="(label,key) in labels" :key="key" :value="key" :label="label" /></ElSelect></ElFormItem><ElFormItem label="版本号"><ElInput v-model="version" placeholder="例如 1.1.0" maxlength="40" aria-label="Skill 版本号" /></ElFormItem><ElFormItem label="版本包"><input :key="fileKey" type="file" accept=".zip" aria-label="Skill ZIP 包" :disabled="uploading" @change="choose" /></ElFormItem></ElForm>
      <p class="hx-footnote">{{isMockMode?'模拟接收 ZIP 文件并计算校验和，不执行包内容、不安装到服务器。':'上传后由受控安装作业校验包内容和依赖。'}} 上传限制以接口校验结果为准。</p><ElAlert v-if="uploadError" :title="uploadError" type="error" :closable="false" />
      <template #footer><ElButton :disabled="uploading" @click="uploadOpen=false">取消</ElButton><ElButton type="primary" :loading="uploading" :disabled="!file || !version.trim()" @click="upload">上传版本</ElButton></template>
    </ElDialog>
    <ElDialog v-model="detailOpen" title="版本记录" width="560px"><template v-if="selected"><p>版本：{{ selected.version }} · {{ selected.referenced?'已有任务引用':'尚无任务引用' }}</p><p style="overflow-wrap:anywhere">SHA-256：{{ selected.checksum }}</p><p>节点：{{selected.node||'尚未安装'}}</p><p>安装时间：{{selected.installedAt?new Date(selected.installedAt).toLocaleString('zh-CN'):'尚未安装'}}</p><p>最近变更：{{new Date(selected.updatedAt).toLocaleString('zh-CN')}}</p><ElAlert v-if="selected.error" :title="selected.error" type="error" :closable="false" /></template></ElDialog>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listManagedSkills, uploadSkill, installSkill, setSkillStatus } from '@/api/management'
import { isMockMode } from '@/api/hengxin/client'
import type { Mode } from '@/types/hengxin'
import type { ManagedSkill } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { labels } from '../model'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
const {data,loading,error,load}=useAdminQuery(listManagedSkills)
const busy=ref(''),actionError=ref(''),uploadOpen=ref(false),uploading=ref(false),uploadError=ref(''),file=ref<File>(),fileKey=ref(0),version=ref(''),mode=ref<Mode>('wallpaper'),selected=ref<ManagedSkill>(),detailOpen=ref(false)
const statuses={uploaded:'已上传',installing:'安装中',available:'可用',disabled:'已停用',failed:'安装失败'}
let timer:ReturnType<typeof setTimeout>|undefined
watch(data,rows=>{clearTimeout(timer);if(rows?.some(row=>row.status==='installing'))timer=setTimeout(load,1000)});onBeforeUnmount(()=>clearTimeout(timer))
function choose(event:Event){file.value=(event.target as HTMLInputElement).files?.[0]}
async function upload(){if(uploading.value||!file.value)return;uploading.value=true;uploadError.value='';try{await uploadSkill(file.value,mode.value,version.value.trim());uploadOpen.value=false;file.value=undefined;fileKey.value++;version.value='';ElMessage.success('版本包已接收，请安装后使用');await load()}catch(e){uploadError.value=e instanceof Error?e.message:'上传失败，请重试'}finally{uploading.value=false}}
async function action(row:ManagedSkill,run:()=>Promise<ManagedSkill>){if(busy.value)return;busy.value=row.id;actionError.value='';try{const accepted=await run();if(data.value)data.value=data.value.map(item=>item.id===accepted.id?accepted:item);await load()}catch(e){actionError.value=e instanceof Error?e.message:'操作失败，请重试'}finally{busy.value=''}}
function install(row:ManagedSkill){void action(row,()=>installSkill(row.id))}
function publish(row:ManagedSkill){void action(row,()=>setSkillStatus(row.id,'available'))}
async function disable(row:ManagedSkill){try{await ElMessageBox.confirm('停用后新任务不能选择此版本，历史任务的固定引用保留。','停用 Skill',{type:'warning',confirmButtonText:'确认停用',cancelButtonText:'取消'})}catch{return}await action(row,()=>setSkillStatus(row.id,'disabled'))}
const columns=[{prop:'name',label:'Skill / 版本',minWidth:220,useSlot:true},{prop:'status',label:'安装状态',minWidth:170,useSlot:true},{prop:'details',label:'版本信息',minWidth:150,useSlot:true},{prop:'action',label:'操作',minWidth:160,useSlot:true}]
</script>
