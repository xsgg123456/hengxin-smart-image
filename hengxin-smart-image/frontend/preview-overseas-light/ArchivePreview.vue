<template>
  <div class="hx-page">
    <div class="hx-heading"><div><h1>成品库</h1><p>搜索品名、品牌或 SKU，任一项匹配即可。</p></div><ElTag type="success">{{ filtered.length }} 套归档</ElTag></div>
    <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter">
      <ElInput v-model="search" clearable class="hx-search" aria-label="搜索成品" placeholder="搜索品名、品牌、SKU" />
      <ElSelect v-if="!baseline" v-model="archiver" clearable filterable aria-label="归档人筛选" placeholder="全部归档人" style="width:200px"><ElOption v-for="p in people" :key="p.id" :label="p.name" :value="p.id" /></ElSelect>
      <ElButton @click="reset">重置筛选</ElButton><ElButton :loading="refreshing" @click="refresh">刷新成品</ElButton>
    </div><p v-if="!baseline && archiver" class="hx-footnote archive-match">显示 {{ people.find(p => p.id === archiver)?.name }} 曾参与归档的成品，包含多人分批归档。</p></ElCard>
    <p v-if="loading" role="status">正在加载成品…</p>
    <ElAlert v-if="scene === 'error'" title="成品加载失败，请重试。" type="error" :closable="false"><ElButton @click="$emit('retry')">重新加载</ElButton></ElAlert>
    <ElEmpty v-if="!loading && scene !== 'error' && !filtered.length" description="暂无匹配成品；设计归档后的图片会显示在这里"><ElButton v-if="search || archiver" @click="reset">清空筛选</ElButton></ElEmpty>
    <div class="hx-library-grid hx-gap"><ElCard v-for="item in filtered" :key="item.id" class="art-card hx-library-card" shadow="never">
      <div class="archive-cover-layout"><div class="archive-cover"><button class="archive-cover-button" :aria-label="`预览 ${item.productName}`" @click="selected = item"><ElImage :src="item.image" :alt="item.productName + '（预览示意图）'" fit="contain" /><span class="archive-cover-count">共 {{ item.pictureCount }} 张</span></button></div>
        <div class="hx-library-info"><div class="archive-card-status"><ElTag type="success">已归档</ElTag></div><OverseasArchiveFields :archive="item" compact /><p class="hx-footnote">{{ item.pictureCount }} 张图片</p></div>
      </div>
      <dl class="archive-card-audit"><div><dt>{{ baseline ? '归档人' : '最近归档人' }}</dt><dd>{{ item.latestArchive?.actorName }}</dd></div><div><dt>归档时间</dt><dd>{{ formatBeijingTime(item.latestArchive?.at) }}（北京时间）</dd></div><div v-if="!baseline && archiver && item.latestArchive?.actorId !== archiver"><dt>筛选匹配</dt><dd>{{ people.find(p => p.id === archiver)?.name }} 曾参与归档</dd></div></dl>
      <div class="hx-row archive-card-actions"><ElButton text type="primary" @click="selected = item">查看成品</ElButton><ElButton @click="explain">下载整套成品</ElButton></div>
    </ElCard></div>
    <ElDrawer :model-value="!!selected" title="成品详情" size="min(680px, 100vw)" @close="selected = null"><template v-if="selected"><OverseasArchiveFields :archive="selected" /><ElImage class="archive-detail-image" :src="selected.image" fit="contain" alt="成品预览示意图" /><p class="hx-footnote">预览示意图 · 用于展示卡片和归档交互</p><h3 class="hx-gap">归档记录</h3><ElTimeline class="hx-gap"><ElTimelineItem v-for="event in [...selected.history].reverse()" :key="event.id" :timestamp="formatBeijingTime(event.at)"><strong>{{ event.actorName }}</strong> 归档了 {{ event.pictures[0].name }}</ElTimelineItem></ElTimeline></template></ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import OverseasArchiveFields from '@/views/overseas/OverseasArchiveFields.vue'
import { formatBeijingTime } from '@/utils/beijing-time'
import { archives, people, type DemoArchive } from './data'
const props = defineProps<{ baseline: boolean; scene: string }>(), emit = defineEmits<{ retry: [] }>()
const search = ref(''), archiver = ref(''), selected = ref<DemoArchive | null>(null), refreshing = ref(false)
const loading = computed(() => props.scene === 'loading' || refreshing.value)
const filtered = computed(() => props.scene !== 'normal' ? [] : archives.filter(a => (props.baseline || !archiver.value || a.history.some(e => e.actorId === archiver.value)) && (!search.value.trim() || [a.productName, a.brand, ...a.skus.map(s => s.code)].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()))))
function reset() { search.value = ''; archiver.value = '' }
function explain() { ElMessage.info('当前为交互预览，未连接真实成品下载。') }
async function refresh() { refreshing.value = true; await new Promise(resolve => setTimeout(resolve, 400)); refreshing.value = false; emit('retry') }
</script>
