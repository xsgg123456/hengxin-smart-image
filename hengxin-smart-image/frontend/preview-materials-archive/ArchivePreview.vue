<template>
  <div class="hx-page archive-preview-page">
    <div class="hx-heading"><div><h1>成品库</h1><p>搜索品名、品牌或 SKU，任一项匹配即可。</p></div><ElTag type="success">1 套归档</ElTag></div>
    <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter">
      <ElInput v-model="search" clearable class="hx-search" aria-label="搜索成品" placeholder="搜索品名、品牌、SKU" /><ElButton @click="search = ''">重置筛选</ElButton><ElButton @click="refresh">刷新成品</ElButton>
    </div></ElCard>
    <div v-if="matches" class="hx-library-grid hx-gap"><ElCard class="art-card hx-library-card" shadow="never">
      <div class="archive-cover-layout"><div class="archive-cover"><AssetImage :asset="pictures[0]" :group="pictures" title="归档成品" /><span class="archive-cover-count">共 {{ pictures.length }} 张</span></div>
      <div class="hx-library-info"><div class="hx-row"><ElTag>OUTON</ElTag><ElTag type="success">已归档</ElTag></div><h3>直杆实木布罩灯-乡村风</h3><p>H-ZGD0008</p><p class="hx-footnote">Amazon</p><p class="hx-footnote">2 张图片 · 2026-10-16 10:46:34</p></div></div>
      <div class="hx-row archive-card-actions"><ElButton text type="primary" @click="detailOpen = true">查看成品</ElButton><ElButton @click="download">下载整套成品</ElButton></div>
    </ElCard></div>
    <ElEmpty v-else description="暂无匹配成品" />
    <ElPagination v-if="matches" class="hx-gap" layout="prev, pager, next" :current-page="1" :page-size="20" :total="1" />
    <p class="preview-library-note">交互预览 · 沿用现有前端，图片为本地灯具示例。</p>
    <ElDialog v-model="detailOpen" title="归档成品" width="min(1100px, 94vw)" append-to-body>
      <ElButton @click="refresh">刷新成品详情</ElButton>
      <h2 class="hx-gap">直杆实木布罩灯-乡村风</h2><p>OUTON · Amazon · H-ZGD0008</p>
      <p class="hx-footnote">2 张图片 · 归档于 2026-10-16 10:46:34</p>
      <ElButton text type="primary" @click="detailOpen = false; router.push('/overseas/tasks')">查看原任务</ElButton>
      <div class="archive-preview-pictures hx-gap"><ElCard v-for="picture in pictures" :key="picture.id" class="art-card" shadow="never">
        <AssetImage :asset="picture" :group="pictures" title="归档成品" /><p>{{ picture.name }}</p><p class="hx-footnote">H-ZGD0008</p><a :href="picture.url" :download="picture.name">下载图片</a>
      </ElCard></div>
      <template #footer><ElButton @click="detailOpen = false">关闭</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AssetImage from './AssetImage.vue'
import { pictures } from './state'
const router = useRouter(), search = ref(''), detailOpen = ref(false)
const matches = computed(() => '直杆实木布罩灯-乡村风 OUTON H-ZGD0008'.toLowerCase().includes(search.value.trim().toLowerCase()))
function refresh() { ElMessage.success('预览示例已刷新') }
function download() { ElMessage.info('独立预览未连接整套打包接口；可在详情中下载单张样图。') }
</script>
<style scoped>
.hx-library-grid{grid-template-columns:repeat(auto-fill,minmax(min(420px,100%),1fr))}.hx-library-card :deep(.el-card__body){padding:18px}.hx-library-info{padding:0}
.archive-preview-page{padding:24px 28px}.hx-filter>.el-input{width:320px;max-width:100%}.archive-cover-layout{display:flex;align-items:center;gap:18px}.archive-cover{position:relative;flex:0 0 120px;width:120px;height:120px;background:var(--art-gray-100);border:1px solid var(--default-border);border-radius:6px;overflow:hidden}.archive-cover :deep(.el-image){width:120px;height:120px;cursor:zoom-in}.archive-cover-count{position:absolute;bottom:4px;right:4px;background:#0009;color:white;border-radius:4px;padding:1px 6px;font-size:11px;pointer-events:none}.hx-library-info{min-width:0;flex:1}.hx-library-info h3{margin:10px 0 6px;line-height:1.5}.hx-library-info p{margin:6px 0;overflow-wrap:anywhere}.archive-card-actions{margin-top:14px}.preview-library-note{margin-top:16px;color:var(--art-gray-500);font-size:12px}.archive-preview-pictures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.archive-preview-pictures :deep(.el-image){height:210px;width:100%;cursor:zoom-in}.archive-preview-pictures p{margin:8px 0}.archive-preview-pictures a{font-size:13px;color:var(--el-color-primary)}
@media(max-width:600px){.archive-preview-page{padding:12px}.archive-cover-layout{gap:12px}.archive-cover{flex-basis:96px;width:96px;height:96px}.archive-cover :deep(.el-image){width:96px;height:96px}.archive-preview-pictures{grid-template-columns:1fr}.hx-filter>.el-input{width:100%}}
</style>
