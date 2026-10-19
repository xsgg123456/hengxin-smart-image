<template>
  <div class="hx-page archive-preview-page">
    <div class="hx-heading"><div><h1>成品库</h1><p>搜索品名、品牌或 SKU，任一项匹配即可。</p></div><ElTag type="success">1 套归档</ElTag></div>
    <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter"><ElInput v-model="search" clearable aria-label="搜索成品" placeholder="搜索品名、品牌、SKU" /><ElButton @click="search = ''">重置筛选</ElButton><ElButton @click="refresh">刷新成品</ElButton></div></ElCard>
    <div v-if="matches" class="hx-library-grid hx-gap"><ElCard class="art-card hx-library-card" shadow="never">
      <div class="archive-cover-layout"><div class="archive-cover"><AssetImage :asset="pictures[0]" :group="pictures" title="归档成品" /><span>共 {{ pictures.length }} 张</span></div><div class="hx-library-info"><div class="archive-card-status"><ElTag type="success">已归档</ElTag></div><ArchiveFields compact /></div></div>
      <dl class="archive-audit-summary"><div><dt>归档人</dt><dd>{{ latest.actor }}</dd></div><div><dt>归档时间</dt><dd>{{ formatBeijingTime(latest.time) }}</dd></div></dl>
      <p v-if="events.length > 1" class="hx-footnote">显示最近一次归档 · 共 {{ events.length }} 条归档记录</p>
      <div class="hx-row archive-card-actions"><ElButton text type="primary" @click="detailOpen = true">查看成品</ElButton><ElButton @click="downloadHint">下载整套成品</ElButton></div>
    </ElCard></div>
    <ElEmpty v-else description="暂无匹配成品" />
    <ElPagination v-if="matches" class="hx-gap" layout="prev, pager, next" :total="1" :page-size="20" />
    <p class="hx-footnote archive-preview-note">交互预览 · 归档人与时间为示例数据，新增记录仅保留在本页，刷新后重置。</p>
    <ElButton @click="$emit('studio')">返回 AI 设计工作台</ElButton>
    <ElDialog v-model="detailOpen" title="归档成品" width="min(1100px, 94vw)" append-to-body>
      <ElButton @click="refresh">刷新成品详情</ElButton>
      <ArchiveFields />
      <dl class="archive-audit-summary detail-audit"><div><dt>归档人</dt><dd>{{ latest.actor }}</dd></div><div><dt>归档时间</dt><dd>{{ formatBeijingTime(latest.time) }}</dd></div></dl>
      <div class="hx-row"><span class="hx-footnote">{{ pictures.length }} 张图片 · {{ events.length > 1 ? '以上为最近一次归档信息' : '归档信息' }} · 北京时间</span><ElButton text type="primary" @click="source">查看原任务</ElButton></div>
      <details class="archive-history"><summary>归档记录（{{ events.length }}）</summary><div v-for="event in events" :key="event.id" class="archive-event"><strong>{{ event.actor }}</strong><time>{{ formatBeijingTime(event.time) }}</time><span>归档 {{ event.pictures.length }} 张图片</span><p>{{ event.pictures.map(p => p.name).join('、') }}</p></div></details>
      <div class="archive-pictures"><ElCard v-for="picture in pictures" :key="picture.id" class="art-card" shadow="never"><AssetImage :asset="picture" :group="pictures" title="归档成品" /><p>{{ picture.name }}</p><p class="hx-footnote">SKU：{{ product.sku }}</p><a :href="picture.url" :download="picture.name">下载图片</a></ElCard></div>
      <template #footer><ElButton @click="detailOpen = false">关闭</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { formatBeijingTime } from '@/utils/beijing-time'
import AssetImage from '../preview-studio-images/AssetImage.vue'
import ArchiveFields from './ArchiveFields.vue'
import { product, type ArchiveEvent } from './archive-state'
import type { Asset } from '../preview-studio-images/state'
const props = defineProps<{ pictures: Asset[]; events: ArchiveEvent[] }>()
const emit = defineEmits<{ studio: [] }>()
const search = ref(''), detailOpen = ref(false)
const latest = computed(() => props.events[0])
const matches = computed(() => [product.name, product.brand, product.sku].some(v => v.toLowerCase().includes(search.value.trim().toLowerCase())))
function source() { detailOpen.value = false; emit('studio') }
function refresh() { ElMessage.success('已显示本次预览的最新归档记录') }
function downloadHint() { ElMessage.info('预览未接入整套打包，请在成品详情中下载单张样图。') }
</script>
<style scoped>
.archive-preview-page { padding: 24px 28px; }
.hx-filter > .el-input { width: 320px; max-width: 100%; }
.hx-library-grid { grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr)); }
.hx-library-card :deep(.el-card__body) { padding: 18px; }
.archive-cover-layout { display: flex; gap: 18px; align-items: center; }
.archive-cover { width: 120px; height: 120px; position: relative; flex-shrink: 0; }
.archive-cover :deep(.el-image) { width: 100%; height: 100%; border: 1px solid #dce3ef; border-radius: 5px; }
.archive-cover > span { position: absolute; right: 4px; bottom: 4px; padding: 2px 5px; background: #0009; color: white; border-radius: 3px; font-size: 12px; pointer-events: none; }
.hx-library-info { min-width: 0; flex: 1; padding: 0; }
.archive-card-status { display: flex; justify-content: flex-end; }
.archive-audit-summary { display: flex; flex-direction: column; gap: 8px; margin: 12px 0 0; border-top: 1px solid #edf0f5; padding-top: 14px; font-size: 13px; }
.archive-audit-summary > div { display: flex; gap: 16px; }
.archive-audit-summary dt { color: #7b8aab; min-width: 56px; }
.archive-audit-summary dd { margin: 0; overflow-wrap: anywhere; }
.detail-audit { flex-direction: row; gap: 36px; flex-wrap: wrap; margin-bottom: 12px; }
.archive-card-actions { margin-top: 14px; }
.archive-preview-note { margin: 22px 0 12px; }
.archive-history { margin: 12px 0 20px; border: 1px solid #e4e8f0; border-radius: 8px; padding: 10px 14px; }
.archive-history summary { cursor: pointer; color: #7b8aab; }
.archive-event { padding: 12px 0; border-top: 1px solid #edf0f5; margin-top: 10px; display: flex; gap: 12px 20px; flex-wrap: wrap; font-size: 13px; }
.archive-event p { flex-basis: 100%; margin: 0; color: #7b8aab; }
.archive-pictures { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.archive-pictures :deep(.el-image) { width: 100%; height: 210px; }
.archive-pictures p { margin: 10px 0; overflow-wrap: anywhere; }
.archive-pictures a { color: var(--el-color-primary); }
@media (max-width: 600px) { .archive-preview-page { padding: 16px; } .archive-pictures { grid-template-columns: 1fr; } .archive-cover { width: 80px; height: 100px; } .archive-cover-layout { gap: 12px; } }
</style>
