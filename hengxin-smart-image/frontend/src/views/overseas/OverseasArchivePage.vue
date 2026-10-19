<template>
  <div class="hx-heading"><div><h1>成品库</h1><p>搜索品名、品牌或 SKU，任一项匹配即可。</p></div><ElTag type="success">{{ total }} 套归档</ElTag></div>
  <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter">
    <ElInput v-model="search" clearable class="hx-search" aria-label="搜索成品" placeholder="搜索品名、品牌、SKU" /><ElButton @click="reset">重置筛选</ElButton><ElButton :loading="loading" @click="load">刷新成品</ElButton>
  </div></ElCard>
  <p v-if="loading" role="status">正在加载成品…</p><ElAlert v-if="error" :title="error" type="error" :closable="false" />
  <ElEmpty v-if="!loading && !error && !items.length" description="暂无匹配成品；设计归档后的图片会显示在这里" />
  <div class="hx-library-grid hx-gap"><ElCard v-for="item in items" :key="item.id" class="art-card hx-library-card" shadow="never">
    <div class="archive-cover-layout"><OverseasArchiveCover :archive="item" :api="api" @preview="preview = item.id" @failure="fail" />
      <div class="hx-library-info"><div class="archive-card-status"><ElTag type="success">已归档</ElTag></div>
        <OverseasArchiveFields :archive="item" compact />
        <p v-if="item.sourceDeleted || !item.taskId" class="hx-footnote">原任务已删除</p>
        <p class="hx-footnote">{{ item.pictureCount }} 张图片</p>
      </div>
    </div>
    <dl class="archive-card-audit">
      <div><dt>归档人</dt><dd>{{ item.latestArchive?.actorName || '历史记录未记录' }}</dd></div>
      <div><dt>归档时间</dt><dd>{{ item.latestArchive ? `${formatBeijingTime(item.latestArchive.at)}（北京时间）` : '历史记录未记录' }}</dd></div>
    </dl>
    <div class="hx-row archive-card-actions"><ElButton text type="primary" @click="selected = item.id">查看成品</ElButton><ElButton :loading="downloading === item.id" @click="download(item)">下载整套成品</ElButton></div>
  </ElCard></div>
  <ElPagination v-if="!error && total" class="hx-gap" layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" @current-change="page = $event" />
  <OverseasArchiveDetail v-if="selected" :id="selected" :api="api" @close="selected = ''" @source="router.push(`/overseas/tasks/${$event}`)" @failure="fail" />
  <OverseasArchiveViewer v-if="preview" :key="preview" :archive-id="preview" :api="api" :initial-index="0" @close="preview = ''" @failure="fail" />
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { IdentityError } from '@/api/identity/request'
import { saveBlob } from '@/api/overseas/pictures'
import { createArchivesApi, type Archive } from '@/api/overseas/archives'
import OverseasArchiveFields from './OverseasArchiveFields.vue'
import OverseasArchiveDetail from './OverseasArchiveDetail.vue'
import OverseasArchiveCover from './OverseasArchiveCover.vue'
import OverseasArchiveViewer from './OverseasArchiveViewer.vue'
import { archiveError } from '@/api/overseas/archives'
const props = defineProps<{ refresh: number }>(), emit = defineEmits<{ failure: [reason: unknown] }>()
const router = useRouter(), api = createArchivesApi(), items = ref<Archive[]>([]), total = ref(0), page = ref(1), search = ref(''), error = ref(''), loading = ref(false), downloading = ref(''), selected = ref('')
const preview = ref('')
let epoch = 0, alive = true, timer: ReturnType<typeof setTimeout> | undefined
function fail(reason: unknown) { error.value = archiveError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { ++epoch; selected.value = ''; preview.value = ''; items.value = []; total.value = 0; loading.value = false; emit('failure', reason) } }
async function load() {
  const current = ++epoch; loading.value = true; error.value = ''; items.value = []; total.value = 0
  try { const result = await api.list({ search: search.value.trim(), page: page.value, pageSize: 20 }); if (alive && current === epoch) { items.value = result.items; total.value = result.total; if (!items.value.length && page.value > 1 && total.value > 0) page.value = Math.ceil(total.value / 20) } }
  catch (reason) { if (alive && current === epoch) fail(reason) }
  finally { if (current === epoch) loading.value = false }
}
async function download(item: Archive) { if (downloading.value) return; downloading.value = item.id; const current = epoch; try { const blob = await api.download(item.id); if (alive && current === epoch) saveBlob(blob, `${item.productName}.zip`) } catch (reason) { if (alive && current === epoch) fail(reason) } finally { downloading.value = '' } }
function reset() { if (search.value) search.value = ''; else if (page.value !== 1) page.value = 1; else void load() }
watch(search, () => { ++epoch; loading.value = true; error.value = ''; items.value = []; total.value = 0; clearTimeout(timer); timer = setTimeout(() => { if (page.value === 1) void load(); else page.value = 1 }, 250) })
watch([page, () => props.refresh], load, { immediate: true })
onUnmounted(() => { alive = false; ++epoch; clearTimeout(timer); items.value = [] })
</script>
<style scoped>
.hx-filter > .el-input { width: 320px; max-width: 100%; }
.hx-library-grid { grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr)); }
.hx-library-card :deep(.el-card__body) { padding: 18px; }
.archive-cover-layout { display: flex; align-items: center; gap: 18px; }
.hx-library-info { overflow-wrap: anywhere; min-width: 0; flex: 1; padding: 0; }
.hx-library-info h3 { margin: 10px 0 6px; line-height: 1.5; }
.hx-library-info p { margin: 6px 0; }
.archive-card-status { display: flex; justify-content: flex-end; }
.archive-card-audit { border-top: 1px solid var(--el-border-color-lighter); margin: 16px 0 0; padding-top: 12px; font-size: 13px; }
.archive-card-audit > div { display: flex; gap: 16px; margin: 6px 0; line-height: 1.6; }
.archive-card-audit dt { width: 56px; flex-shrink: 0; color: var(--el-text-color-secondary); }
.archive-card-audit dd { margin: 0; overflow-wrap: anywhere; }
.archive-card-actions { margin-top: 14px; }
@media (max-width: 600px) { .hx-filter > .el-input { width: 100%; max-width: none; } .archive-cover-layout { gap: 12px; } }
</style>
