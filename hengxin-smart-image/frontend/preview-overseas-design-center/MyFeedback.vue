<template>
  <div v-loading="loading" class="personal-feedback">
    <ElAlert v-if="failed" title="读取反馈失败" type="error" :closable="false"><ElButton link @click="load">重新加载</ElButton></ElAlert>
    <ElEmpty v-else-if="!loading && !items.length" description="你还没有提交过反馈" />
    <article v-for="item in items" :key="item.id" class="personal-item">
      <header><span>{{formatBeijingTime(item.createdAt)}}<small v-if="item.sample">示例</small></span>
        <ElTag size="small" :type="item.status==='待处理'?'warning':item.status==='处理中'?'primary':'success'">{{ item.status }}</ElTag>
      </header>
      <p class="personal-question">{{item.description}}</p>
      <p class="personal-source">{{item.source}}</p>
      <div v-if="item.reply" class="personal-reply"><strong>管理员回复</strong><p>{{ item.reply }}</p></div>
      <p v-else class="personal-wait">暂无管理员回复</p>
    </article>
  </div>
</template>
<script setup lang="ts">
import { onMounted,onUnmounted,ref } from 'vue'
import { listMyFeedback,type PersonalFeedback } from './feedback'
import { formatBeijingTime } from '@/utils/beijing-time'
const items=ref<PersonalFeedback[]>([]),loading=ref(false),failed=ref(false)
async function load(){
  loading.value=true
  try{items.value=await listMyFeedback();failed.value=false}
  catch{failed.value=true}
  finally{loading.value=false}
}
onMounted(()=>{load();window.addEventListener('focus',load)})
onUnmounted(()=>window.removeEventListener('focus',load))
</script>
<style scoped>
.personal-feedback{min-height:80px}.personal-item{padding:18px 0;border-bottom:1px solid var(--el-border-color-lighter)}
.personal-item:first-child{padding-top:4px}.personal-item header{display:flex;justify-content:space-between;gap:8px;align-items:center;color:var(--el-text-color-secondary);font-size:12px}
.personal-item small{margin-left:8px}.personal-question,.personal-reply p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65}
.personal-question{margin:10px 0 4px;color:var(--el-text-color-primary);font-size:15px}.personal-source,.personal-wait{font-size:12px;color:var(--el-text-color-secondary)}.personal-wait{margin:10px 0 0}
.personal-reply{margin-top:12px;padding:10px 14px;background:var(--el-fill-color-light);border-radius:7px;font-size:13px}.personal-reply strong{font-size:12px;font-weight:600}.personal-reply p{margin:4px 0 0}
</style>
