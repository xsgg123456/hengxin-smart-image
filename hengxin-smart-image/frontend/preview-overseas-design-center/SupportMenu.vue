<template>
  <Teleport v-if="mounted" to=".layout-sidebar .menu-left">
    <nav class="support-menu" aria-label="帮助与信息">
      <button type="button" title="意见反馈" aria-label="意见反馈" :class="{selected: open}" @click="start">
        <ElIcon><ChatLineSquare /></ElIcon><span>意见反馈</span>
      </button>
      <button type="button" title="关于我们" aria-label="关于我们" :class="{selected: route.path === '/overseas/about' && !open}" @click="about">
        <ElIcon><InfoFilled /></ElIcon><span>关于我们</span>
      </button>
    </nav>
  </Teleport>
  <ElDrawer v-model="open" title="意见反馈" size="min(450px, 100vw)" append-to-body>
    <ElTabs v-model="tab" class="support-tabs">
      <ElTabPane label="提交反馈" name="create">
    <ElForm label-position="top" class="support-form" @submit.prevent="submit">
      <ElFormItem label="反馈页面"><span class="support-source">{{ source }}</span></ElFormItem>
      <ElFormItem label="问题描述" required :error="error">
        <ElInput v-model="description" aria-label="问题描述" type="textarea" :rows="5" maxlength="2000"
          show-word-limit placeholder="你进行了什么操作？页面出现了什么问题？" @input="error=''" />
      </ElFormItem>
      <ElFormItem label="问题截图（选填）">
        <label v-if="!picture" class="support-upload"><ElIcon><Upload /></ElIcon> 添加截图<input type="file" accept="image/png,image/jpeg,image/webp" aria-label="添加截图" @change="attach"></label>
        <div v-else class="support-image"><img :src="url" alt="已选问题截图"><div>{{ picture.name }} <ElButton link type="danger" @click="clearPicture">移除</ElButton></div></div>
      </ElFormItem>
    </ElForm>
      </ElTabPane>
      <ElTabPane label="我的反馈" name="mine">
        <MyFeedback v-if="open && tab==='mine'" />
      </ElTabPane>
    </ElTabs>
    <template #footer><div v-if="tab==='create'" class="support-footer"><small>预览反馈仅保存在当前浏览器</small><ElButton @click="open=false">取消</ElButton><ElButton type="primary" :loading="busy" @click="submit">提交反馈</ElButton></div><ElButton v-else @click="open=false">关闭</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatLineSquare, InfoFilled, Upload } from '@element-plus/icons-vue'
import { useSettingStore } from '@/store/modules/setting'
import MyFeedback from './MyFeedback.vue'
import { addFeedback } from './feedback'
const emit = defineEmits<{ submitted: [] }>()
const props = defineProps<{source:string}>()
const route=useRoute(), router=useRouter(),settings=useSettingStore()
const tab=ref('create')
const open=ref(false), mounted=ref(false),busy=ref(false),error=ref(''),description=ref(''),url=ref(''),picture=ref<File>()
onMounted(()=>{mounted.value=true})
watch(()=>route.query.feedback,value=>{if(value==='mine'){tab.value='mine';open.value=true}}, {immediate:true})
onUnmounted(clearPicture)
function closeMobileMenu(){if(window.innerWidth<800) settings.setMenuOpen(false)}
function start(){closeMobileMenu();tab.value='create';open.value=true}
function about(){closeMobileMenu();router.push('/overseas/about')}
function clearPicture(){if(url.value)URL.revokeObjectURL(url.value);url.value='';picture.value=undefined}
function attach(event:Event){
  const input=event.target as HTMLInputElement,file=input.files?.[0]
  if(!file)return
  if(!['image/png','image/jpeg','image/webp'].includes(file.type)){ElMessage.warning('请选择 PNG、JPG 或 WebP 图片');input.value='';return}
  clearPicture();picture.value=file;url.value=URL.createObjectURL(file)
}
async function submit(){
  if(busy.value)return
  if(!description.value.trim()){error.value='请填写问题描述';return}
  const record={source:props.source,description:description.value.trim(),picture:picture.value,createdAt:new Date().toISOString()}
  busy.value=true
  try{
    await addFeedback(record)
    emit('submitted')
    tab.value='mine';description.value='';clearPicture();ElMessage.success('反馈已保存到本地预览')
  }catch{ElMessage.error('本地保存失败，请重试')}
  finally{busy.value=false}
}
</script>
<style>
.menu-left:has(.support-menu) > .el-scrollbar{max-height:calc(100% - 180px)}
.support-menu{position:absolute;bottom:10px;left:8px;right:8px;padding-top:8px;border-top:1px solid var(--el-border-color-lighter);display:grid;gap:3px}
.support-menu button{height:42px;border:0;border-radius:6px;display:flex;align-items:center;gap:10px;padding:0 14px;background:transparent;color:var(--el-text-color-regular);font:inherit;font-size:14px;cursor:pointer}
.support-menu .el-icon{font-size:17px}.support-menu button:hover{background:var(--el-fill-color-light)}.support-menu button.selected{background:var(--el-color-primary-light-9);color:var(--el-color-primary)}
.menu-left-close .support-menu button{justify-content:center;padding:0}.menu-left-close .support-menu button span{display:none}
.support-form .el-form-item{margin-bottom:24px}.support-source{color:var(--el-text-color-secondary);font-size:13px}
.support-upload{position:relative;display:inline-flex;align-items:center;gap:8px;padding:4px 14px;border:1px dashed var(--el-border-color);border-radius:6px;cursor:pointer}
.support-upload input{position:absolute;inset:0;opacity:0;width:100%;cursor:pointer}.support-upload:focus-within{outline:2px solid var(--el-color-primary)}
.support-image{min-width:0;overflow-wrap:anywhere}.support-image img{display:block;max-width:100%;max-height:180px;object-fit:contain}
.support-footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}.support-footer small{margin-right:auto;color:var(--el-text-color-secondary)}.support-footer button+button{margin-left:0}
.about-card{margin-top:24px}.about-card .el-card__body{text-align:center;padding:64px 24px}.about-logo{width:44px;height:44px;margin:0 auto 16px}.about-card h2{font-size:18px;font-weight:600}.about-card p{color:var(--el-text-color-secondary);font-size:14px;margin-top:8px}
</style>


