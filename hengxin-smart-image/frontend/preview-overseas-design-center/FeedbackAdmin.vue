<template>
  <section class="dc-page hx-page">
    <header class="dc-title"><h1>反馈管理</h1><p>查看用户反馈的问题、来源页面和截图，记录处理进展。</p></header>
    <ElCard class="art-card feedback-card" shadow="never">
      <div class="feedback-filter"><ElRadioGroup v-model="filter" aria-label="反馈状态筛选">
        <ElRadioButton v-for="label in filters" :key="label" :value="label">{{ label }} {{ count(label) }}</ElRadioButton>
      </ElRadioGroup><ElButton :loading="loading" @click="load">刷新</ElButton></div>
      <ElAlert v-if="loadError" type="error" :closable="false" :title="loadError"/>
      <ElTable :data="shown" row-key="id" empty-text="暂无此状态的反馈">
        <ElTableColumn label="问题描述" min-width="235"><template #default="{row}">
          <span v-if="row.sample" class="feedback-sample">示例</span>{{ row.description }}
        </template></ElTableColumn>
        <ElTableColumn prop="source" label="反馈页面" min-width="155"/>
        <ElTableColumn label="提交人" width="100"><template #default="{row}">{{ row.reporter || '未记录' }}</template></ElTableColumn>
        <ElTableColumn label="提交时间" width="164"><template #default="{row}">{{ formatBeijingTime(row.createdAt) }}</template></ElTableColumn>
        <ElTableColumn label="状态" width="95"><template #default="{row}">
          <ElTag :type="row.status==='待处理'?'warning':row.status==='处理中'?'primary':'success'">{{row.status}}</ElTag>
        </template></ElTableColumn>
        <ElTableColumn fixed="right" label="操作" width="95"><template #default="{row}">
          <ElButton type="primary" link @click="inspect(row)">{{row.status==='已处理'?'查看详情':'查看处理'}}</ElButton>
        </template></ElTableColumn>
      </ElTable>
    </ElCard>
    <ElDrawer v-model="open" title="反馈详情" size="min(500px, 100vw)" append-to-body>
      <template v-if="current">
        <div class="feedback-metadata"><span>{{ current.reporter || '提交人未记录' }}</span><span>{{formatBeijingTime(current.createdAt)}}</span><ElTag v-if="current.sample" type="info" size="small">示例反馈</ElTag></div>
        <p class="feedback-source">反馈页面 · {{current.source}}</p>
        <h3 class="feedback-heading">问题描述</h3><p class="feedback-description">{{current.description}}</p>
        <template v-if="imageUrl"><h3 class="feedback-heading">问题截图</h3><ElImage class="feedback-picture" :src="imageUrl" fit="contain" :preview-src-list="[imageUrl]" preview-teleported alt="用户提交的问题截图" /></template>
        <ElDivider/>
        <ElForm label-position="top">
          <ElFormItem label="处理状态"><ElRadioGroup v-model="status" aria-label="处理状态"><ElRadioButton v-for="s in statuses" :key="s" :value="s">{{s}}</ElRadioButton></ElRadioGroup></ElFormItem>
          <ElFormItem label="回复提交人" :required="status==='已处理'" :error="error">
            <ElInput v-model="reply" aria-label="回复提交人" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="告诉提交人处理进展或解决方法" @input="error=''"/>
          </ElFormItem>
          <ElFormItem label="内部备注（仅管理员可见）">
            <ElInput v-model="note" aria-label="内部备注" type="textarea" :rows="2" maxlength="2000" placeholder="记录内部排查细节"/>
          </ElFormItem>
        </ElForm>
        <small v-if="current.updatedAt" class="feedback-source">最近处理于 {{formatBeijingTime(current.updatedAt)}}</small>
      </template>
      <template #footer><ElButton @click="open=false">关闭</ElButton><ElButton type="primary" :loading="saving" @click="save">保存处理</ElButton></template>
    </ElDrawer>
  </section>
</template>
<script setup lang="ts">
import { computed,onMounted,onUnmounted,ref,watch } from 'vue'
import { ElMessage } from 'element-plus'
import { formatBeijingTime } from '@/utils/beijing-time'
import { listFeedback,processFeedback,statuses,type Feedback,type Status } from './feedback'
const props=defineProps<{refresh:number}>()
type Filter=Status|'全部'
const filters:Filter[]=['全部',...statuses]
const items=ref<Feedback[]>([]),filter=ref<Filter>('全部'),current=ref<Feedback>()
const loading=ref(false),saving=ref(false),open=ref(false),status=ref<Status>('待处理')
const reply=ref(''),note=ref(''),error=ref(''),loadError=ref(''),imageUrl=ref('')
const shown=computed(()=>filter.value==='全部'?items.value:items.value.filter(i=>i.status===filter.value))
function count(s:Filter){return s==='全部'?items.value.length:items.value.filter(i=>i.status===s).length}
async function load(){
  loading.value=true;loadError.value=''
  try {items.value=await listFeedback()} catch {loadError.value='反馈读取失败，请点击刷新重试。'}
  finally {loading.value=false}
}
function releaseImage(){if(imageUrl.value)URL.revokeObjectURL(imageUrl.value);imageUrl.value=''}
function inspect(row:Feedback){
  current.value=row;status.value=row.status;note.value=row.note || '';reply.value=row.reply || '';error.value=''
  releaseImage();if(row.picture)imageUrl.value=URL.createObjectURL(row.picture)
  open.value=true
}
async function save(){
  if(!current.value || saving.value)return
  if(status.value==='已处理' && !reply.value.trim()){error.value='请填写给提交人的处理结果';return}
  saving.value=true
  try{await processFeedback(current.value,status.value,note.value.trim(),reply.value.trim());open.value=false;ElMessage.success('处理记录已保存')}
  catch(reason){ElMessage.error(reason instanceof Error?reason.message:'保存失败，请重试')}
  finally{saving.value=false;await load()}
}
watch(()=>props.refresh,load)
watch(open,value=>{if(!value)releaseImage()})
onMounted(()=>{load();window.addEventListener('focus',load)})
onUnmounted(()=>{releaseImage();window.removeEventListener('focus',load)})
</script>
<style scoped>
.feedback-card{margin-top:24px}.feedback-filter{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.feedback-sample{margin-right:8px;color:var(--el-text-color-secondary);font-size:12px}
.feedback-metadata{display:flex;align-items:center;flex-wrap:wrap;gap:12px;font-size:13px;color:var(--el-text-color-regular)}
.feedback-source{color:var(--el-text-color-secondary);font-size:13px;margin-top:8px;overflow-wrap:anywhere}
.feedback-heading{font-size:14px;font-weight:600;margin:22px 0 10px}.feedback-description{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}
.feedback-picture{max-width:100%;max-height:200px;border:1px solid var(--el-border-color-light);border-radius:8px}.feedback-picture :deep(img){max-height:190px}
</style>
