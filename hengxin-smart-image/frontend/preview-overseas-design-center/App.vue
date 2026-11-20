<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="outside">切换业务</ElButton><ElButton text @click="outside">退出登录</ElButton></template>
    <div class="layout-content">
      <StudioPage v-if="active" :key="active.id" :task="active" @back="goList" />
      <DesignCenter v-else-if="route.path === center" can-create can-read :listing="listing"
        @view="tab => tab === 'tasks' ? goList() : goHome()" @choose="chosen=$event" @custom="chosen='custom'">
        <TaskList v-model:query="query" v-model:status="status" v-model:scope="scope"
          v-model:designer="designer" :assignees="assignees" :tasks="rows" :total="rows.length"
          :allowed="false" :busy="false" @open="openTask" @refresh="refreshList">
          <template #platform><ElSelect v-model="designType" clearable placeholder="全部设计类型" aria-label="设计类型筛选" style="width:155px">
            <ElOption v-for="p in TASK_DESIGN_TYPES" :key="p.value" :value="p.value" :label="p.label" />
          </ElSelect></template>
        </TaskList>
      </DesignCenter>
      <FeedbackAdmin v-else-if="route.path === '/overseas/admin/feedback'" :refresh="feedbackRevision" />
      <section v-else-if="route.path === '/overseas/about'" class="dc-page hx-page"><header class="dc-title"><h1>关于我们</h1></header><ElCard shadow="never" class="art-card about-card"><ArtLogo class="about-logo" /><h2>公司介绍</h2><p>公司介绍正在准备中。</p></ElCard></section>
      <div v-else class="hx-page"><ElEmpty :description="route.params.id ? '此浏览器中未找到该预览任务' : '此页面不在本次设计任务中心预览范围内'"><ElButton @click="goHome">返回设计任务中心</ElButton></ElEmpty></div>
    </div>
    <SupportMenu @submitted="feedbackRevision++" :source="active ? 'AI 设计工作台 · ' + active.title + ' · ' + active.sku : (route.meta.title || '设计任务中心') + (listing ? ' · 继续任务' : '')" />
    <CustomDesignDialog v-if="chosen === 'custom'" actor-id="design-center-preview" :create="createCustom" @close="chosen=''" @created="openTask" />
    <CreateDialog v-else-if="chosen" :key="chosen" :platform="chosen" @close="chosen=''" @submit="createTask" />
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import { TASK_DESIGN_TYPES } from '@/views/overseas/platforms'
import { parseCustomTaskInput } from '@/api/overseas/tasks'
import { randomUUID } from '@/utils/browser-crypto'
import CustomDesignDialog from '@/views/overseas/center/CustomDesignDialog.vue'
import DesignCenter from '@/views/overseas/center/DesignCenter.vue'
import CreateDialog from './CreateDialog.vue'
import StudioPage from './StudioPage.vue'
import FeedbackAdmin from './FeedbackAdmin.vue'
import SupportMenu from './SupportMenu.vue'
import ArtLogo from '@/components/core/base/art-logo/index.vue'
import TaskList from './TaskList.vue'
import { readTasks, persistTasks } from './tasks'
import type { CreateSubmission } from './form-data'
const route=useRoute(),router=useRouter(),center='/overseas/design-center'
const feedbackRevision=ref(0)
const chosen=ref(''),tasks=ref(readTasks()),query=ref(''),status=ref(''),scope=ref('all'),designer=ref(''),designType=ref('')
const listing=computed(()=>route.query.view==='tasks')
const active=computed(()=>tasks.value.find(t=>t.id===route.params.id))
const assignees=['张帅','林悦'].map(name=>({id:name,name}))
const rows=computed(()=>tasks.value.filter(t=>(!designType.value || (t.designType === 'custom' ? 'custom' : t.platform) === designType.value)
  && (!designer.value || designer.value===t.designer) && (scope.value==='all' || t.designer==='张帅')
  && (!status.value || status.value==='designing')
  && [t.title,t.productName,t.sku,t.brand].some(v=>v?.toLowerCase().includes(query.value.trim().toLowerCase())))
  .map(t=>({...t,name:t.title,status:'studio' as const,designer:{id:t.designer,name:t.designer},skus:[{code:t.sku}]})))
watch(()=> route.fullPath, ()=>{chosen.value=''})
function goHome(){router.push(center)}
function goList(){router.push({path:center,query:{view:'tasks'}})}
function openTask(id:string){router.push(center+'/task/'+encodeURIComponent(id))}
function refreshList(){tasks.value=[...tasks.value];ElMessage.success('任务列表已刷新')}
function createTask(data:CreateSubmission){
  const task={...data,id:'HX-N'+randomUUID(),createdAt:new Date().toISOString()}
  tasks.value.unshift(task);persistTasks(tasks.value);chosen.value='';openTask(task.id)
}
async function createCustom(value:string, key:string) {
  const existing = tasks.value.find(t => t.requestKey === key)
  if (existing) return existing
  const { productName, sku } = parseCustomTaskInput(value)
  const task = { id: 'HX-N'+randomUUID(), title: value, designType: 'custom' as const, productName, sku,
    brand: '', platform: '', language: '', designer: '张帅', createdAt: new Date().toISOString(), requestKey: key }
  const updated = [task, ...tasks.value]
  persistTasks(updated)
  tasks.value = updated
  return task
}
function outside(){ElMessage.info('当前为本地设计任务中心预览')}
</script>



