<template>
  <div class="hx-heading"><div><h1>成品库</h1><p>按品名 → 品牌 → SKU 查找海外成品。</p></div><ElTag type="success">{{ total }} 套归档</ElTag></div>
  <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter">
    <ElInput v-model="product" clearable aria-label="筛选品名" placeholder="品名" /><ElInput v-model="brand" clearable aria-label="筛选品牌" placeholder="品牌" /><ElInput v-model="sku" clearable aria-label="筛选 SKU" placeholder="SKU" /><ElInput v-model="search" clearable class="hx-search" aria-label="搜索成品" placeholder="搜索品名、品牌、SKU" /><ElButton @click="reset">重置筛选</ElButton><ElButton :loading="loading" @click="load">刷新成品</ElButton>
  </div></ElCard>
  <p v-if="loading" role="status">正在加载成品…</p><ElAlert v-if="error" :title="error" type="error" :closable="false" />
  <ElEmpty v-if="!loading && !error && !items.length" description="暂无匹配成品；设计归档后的图片会显示在这里" />
  <div class="hx-library-grid hx-gap"><ElCard v-for="item in items" :key="item.id" class="art-card hx-library-card" shadow="never"><div class="hx-library-info"><div class="hx-row"><ElTag>{{ item.brand }}</ElTag><ElTag type="success">已归档</ElTag></div><h3>{{ item.productName }}</h3><p>{{ item.skus.map(s => s.code).join(' · ') }}</p><p v-if="item.sourceDeleted || !item.taskId" class="hx-footnote">原任务已删除</p><p class="hx-footnote">{{ item.platform }}</p><p class="hx-footnote">{{ item.pictureCount }} 张图片 · {{ formatBeijingTime(item.createdAt) }}</p><div class="hx-row"><ElButton text type="primary" @click="selected = item.id">查看成品</ElButton><ElButton :loading="downloading === item.id" @click="download(item)">下载整套成品</ElButton></div></div></ElCard></div>
  <ElPagination v-if="!error && total" class="hx-gap" layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" @current-change="page = $event" />
  <OverseasArchiveDetail v-if="selected" :id="selected" :api="api" @close="selected = ''" @source="router.push(`/overseas/tasks/${$event}`)" @failure="fail" />
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { IdentityError } from '@/api/identity/request'
import { saveBlob } from '@/api/overseas/pictures'
import { createArchivesApi, type Archive } from '@/api/overseas/archives'
import OverseasArchiveDetail from './OverseasArchiveDetail.vue'
import { archiveError } from '@/api/overseas/archives'
const props = defineProps<{ refresh: number }>(), emit = defineEmits<{ failure: [reason: unknown] }>()
const router = useRouter(), api = createArchivesApi(), items = ref<Archive[]>([]), total = ref(0), page = ref(1), product = ref(''), brand = ref(''), sku = ref(''), search = ref(''), error = ref(''), loading = ref(false), downloading = ref(''), selected = ref('')
let epoch = 0, alive = true, timer: ReturnType<typeof setTimeout> | undefined
function fail(reason: unknown) { error.value = archiveError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { ++epoch; selected.value = ''; items.value = []; total.value = 0; emit('failure', reason) } }
async function load() {
  const current = ++epoch; loading.value = true; error.value = ''; items.value = []; total.value = 0
  try { const result = await api.list({ product: product.value.trim(), brand: brand.value.trim(), sku: sku.value.trim(), search: search.value.trim(), page: page.value, pageSize: 20 }); if (alive && current === epoch) { items.value = result.items; total.value = result.total; if (!items.value.length && page.value > 1 && total.value > 0) page.value = Math.ceil(total.value / 20) } }
  catch (reason) { if (alive && current === epoch) fail(reason) }
  finally { if (current === epoch) loading.value = false }
}
async function download(item: Archive) { if (downloading.value) return; downloading.value = item.id; const current = epoch; try { const blob = await api.download(item.id); if (alive && current === epoch) saveBlob(blob, `${item.productName}.zip`) } catch (reason) { if (alive && current === epoch) fail(reason) } finally { downloading.value = '' } }
function reset() { product.value = ''; brand.value = ''; sku.value = ''; search.value = '' }
watch([product, brand, sku, search], () => { ++epoch; items.value = []; total.value = 0; clearTimeout(timer); timer = setTimeout(() => { if (page.value === 1) void load(); else page.value = 1 }, 250) })
watch([page, () => props.refresh], load, { immediate: true })
onUnmounted(() => { alive = false; ++epoch; clearTimeout(timer); items.value = [] })
</script>
<style scoped>
.hx-filter > .el-input { width: 180px; }
.hx-library-info { overflow-wrap: anywhere; }
@media (max-width: 600px) { .hx-filter > .el-input { width: 100%; max-width: none; } }
</style>
