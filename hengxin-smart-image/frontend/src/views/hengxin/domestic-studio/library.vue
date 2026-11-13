<template>
  <section class="hx-page domestic-library">
    <div class="hx-heading"><div><span class="hx-admin-kicker">PRODUCT LIBRARY</span><h1>成品库</h1><p>集中查看「相机配件生成」和「手机壳生成」的归档。</p></div><ElTag>{{ total }} 套归档</ElTag></div>
    <div class="domestic-library-filters"><ElInput v-model="search" clearable aria-label="搜索产品名称" placeholder="搜索产品名称" :prefix-icon="Search" /><ElSelect v-model="source" aria-label="归档来源"><ElOption label="全部来源" value="" /><ElOption label="相机配件生成" value="camera" /><ElOption label="手机壳生成" value="case" /></ElSelect><ElButton @click="reset">重置</ElButton></div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton @click="load">重试</ElButton></ElAlert>
    <div v-if="loading && !items.length" class="domestic-library-empty">正在加载归档…</div>
    <div v-else-if="!items.length && !error" class="domestic-library-empty"><p>{{ search || source ? '没有找到匹配的产品' : '暂无归档' }}</p><small>{{ search || source ? '试试其他产品名称或来源。' : '在新品生成工作台完成设计后，点击「归档到成品库」。' }}</small></div>
    <div v-else class="domestic-library-grid"><article v-for="item in items" :key="item.id" class="domestic-library-card"><div class="library-card-title"><h2>{{ item.productName }}</h2><ElTag :type="item.deletionStatus ? 'warning' : 'success'" size="small">{{ item.deletionStatus === 'deleting' ? '删除中' : item.deletionStatus === 'delete_failed' ? '删除失败' : '已归档' }}</ElTag></div><p>{{ sourceTitle(item.workspace) }}</p><dl><div><dt>原会话</dt><dd>{{ item.conversationName }}</dd></div><div><dt>归档时间</dt><dd>{{ formatBeijingTime(item.createdAt, '时间未记录') }}</dd></div><div><dt>成品图片</dt><dd>{{ item.pictureCount }} 张</dd></div></dl><p v-if="item.deletionError">{{ item.deletionError }}</p><div class="library-card-actions"><ElButton type="primary" plain :disabled="!!item.deletionStatus" @click="view(item)">查看归档</ElButton><ElButton v-if="isAdmin" text type="danger" :disabled="item.deletionStatus === 'deleting'" @click="remove(item)">{{ item.deletionStatus === 'delete_failed' ? '重试删除' : '删除' }}</ElButton></div></article></div>
    <ElPagination v-if="total > 20" class="library-pagination" :current-page="page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="page = $event" />
    <ElDrawer :model-value="!!selected || detailLoading" title="归档详情" size="min(760px,100vw)" @close="closeDetail">
      <p v-if="detailLoading">正在加载归档…</p><template v-if="selected"><h2 class="archive-detail-title">{{ selected.productName }}</h2><p class="archive-detail-meta">{{ sourceTitle(selected.workspace) }} · {{ formatBeijingTime(selected.createdAt, '时间未记录') }}</p><ElTabs v-model="tab"><ElTabPane label="成品图片" name="pictures"><ElButton v-if="pictures.length" plain @click="api.download(selected.id)">下载 ZIP</ElButton><div v-if="pictures.length" class="library-pictures"><StudioAssetImage v-for="asset in pictures" :key="asset.id" :asset="asset" :group="pictures" title="归档成品图片" @failure="failure" /></div><ElEmpty v-else description="暂无成品图片" /></ElTabPane><ElTabPane label="对话与资料" name="conversation"><p class="archive-detail-note">归档时保存的副本，后续对话修改不会影响这里。</p><template v-for="turn in selected.turns" :key="turn.id"><article class="studio-message user"><div class="studio-message-name">{{ turn.actorName || '未知操作人' }} <small>{{ formatBeijingTime(turn.createdAt, '时间未记录') }}</small></div><div class="studio-bubble"><p>{{ turn.text }}</p><StudioAttachments :assets="assets([...turn.attachments, ...turn.referencePictures])" title="归档附件" @failure="failure" /><ElButton v-if="turn.imageEdits?.length" text type="primary" @click="history = turn">查看本轮修改材料（{{ turn.imageEdits.length }}张）</ElButton></div></article><article class="studio-message assistant"><div class="studio-message-name">Codex <small>{{ turn.status ? statusLabels[turn.status] : '状态未记录' }}</small><small v-if="turn.replyAt">{{ formatBeijingTime(turn.replyAt, '时间未记录') }}</small></div><div class="studio-bubble"><StudioProcess :turn="{ status: turn.status || 'unknown', reply: turn.reply }" :entries="archiveTranscript(turn)" /><ElAlert v-if="turn.error" :title="`归档时：${turn.error}`" type="error" :closable="false" /><StudioAttachments :assets="assets([...turn.pictures, ...turn.outputs])" title="归档文件" @failure="failure" /></div></article></template></ElTabPane></ElTabs></template>
    </ElDrawer>
    <ElDialog :model-value="!!history" title="本轮修改材料" width="min(980px,94vw)" append-to-body class="batch-review-dialog" @update:model-value="!$event && (history = undefined)"><StudioRevisionDetails v-if="history" :items="archiveRevisions(history)" @failure="failure" /><template #footer><ElButton @click="history = undefined">关闭</ElButton></template></ElDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/modules/user'
import { IdentityError } from '@/api/identity/request'
import { createDomesticArchivesApi, type ArchiveDetail, type ArchiveFile, type ArchiveSummary, type ArchiveTurn } from '@/api/hengxin/domestic-archives'
import { overseasImageCache } from '@/api/shared/image-cache'
import type { Asset } from '@/api/shared/studio'
import { formatBeijingTime } from '@/utils/beijing-time'
import StudioAssetImage from '@/views/shared/studio/StudioAssetImage.vue'
import StudioAttachments from '@/views/shared/studio/StudioAttachments.vue'
import StudioProcess from '@/views/shared/studio/StudioProcess.vue'
import { archiveTranscript } from './archive-transcript'
import StudioRevisionDetails from '@/views/shared/studio/StudioRevisionDetails.vue'
import { historicalRevisions } from '@/views/shared/studio/studio-revisions'
import '@/views/shared/studio/editing/style.css'
const user = useUserStore(), api = createDomesticArchivesApi()
const isAdmin = computed(() => user.getUserInfo.roles?.includes('super_admin'))
overseasImageCache.setIdentity(`domestic:${String(user.getUserInfo.userId || '')}`)
const sourceTitle = (value: string) => value === 'camera' ? '相机配件生成' : '手机壳生成'
const statusLabels = { succeeded: '已回复', partial: '部分完成', failed: '执行失败', cancelled: '已停止' }
const items = ref<ArchiveSummary[]>([]), total = ref(0), page = ref(1), search = ref(''), source = ref('')
const selected = ref<ArchiveDetail>(), history = ref<ArchiveTurn>(), detailLoading = ref(false), loading = ref(false), error = ref(''), tab = ref('pictures')
let sequence = 0, detailSequence = 0, timer: ReturnType<typeof setTimeout> | undefined, poll: ReturnType<typeof setTimeout> | undefined, alive = true
const assets = (rows: ArchiveFile[]): Asset[] => rows.map(row => ({ id: 'upload:' + row.id, name: row.name, contentType: row.contentType, sizeBytes: row.sizeBytes, url: row.url, source: 'upload' }))
const pictures = computed(() => selected.value ? assets(selected.value.turns.flatMap(turn => turn.pictures)) : [])
function archiveRevisions(turn: ArchiveTurn) {
  return historicalRevisions({ imageEdits: turn.imageEdits, attachments: assets(turn.attachments),
    referencePictures: turn.referencePictures.map(item => ({ id: item.id, name: item.name, url: item.url,
      width: item.width ?? 0, height: item.height ?? 0, turnId: turn.id, sku: null, archived: true })) })
}
function failure(reason: unknown) { if (reason instanceof IdentityError && [401, 403].includes(reason.status)) ElMessage.error(reason.message) }
async function load() {
  const current = ++sequence; clearTimeout(poll); loading.value = true; error.value = ''
  try { const result = await api.list(search.value.trim(), source.value, page.value); if (!alive || current !== sequence) return; items.value = result.items; total.value = result.total; if (items.value.some(item => item.deletionStatus === 'deleting')) poll = setTimeout(load, 1500) }
  catch (reason) { if (alive && current === sequence) { error.value = reason instanceof Error ? reason.message : '加载归档失败'; failure(reason) } }
  finally { if (alive && current === sequence) loading.value = false }
}
watch([search, source], () => { page.value = 1; clearTimeout(timer); timer = setTimeout(load, 250) })
watch(page, load)
function reset() { search.value = ''; source.value = ''; page.value = 1; void load() }
async function view(item: ArchiveSummary) { const current = ++detailSequence; selected.value = undefined; detailLoading.value = true; tab.value = 'pictures'; try { const result = await api.detail(item.id); if (alive && current === detailSequence) selected.value = result } catch (reason) { if (alive && current === detailSequence) { ElMessage.error(reason instanceof Error ? reason.message : '加载归档失败'); failure(reason) } } finally { if (alive && current === detailSequence) detailLoading.value = false } }
function closeDetail() { ++detailSequence; selected.value = undefined; history.value = undefined; detailLoading.value = false }
async function remove(item: ArchiveSummary) {
  try { await ElMessageBox.confirm(`删除「${item.productName}」的归档副本？原会话不受影响。`, '删除归档', { type: 'warning', confirmButtonText: item.deletionStatus === 'delete_failed' ? '重试删除' : '确认删除', cancelButtonText: '取消' }); await api.remove(item.id); if (selected.value?.id === item.id) closeDetail(); await load() }
  catch (reason) { if (reason !== 'cancel' && reason !== 'close') ElMessage.error(reason instanceof IdentityError && typeof reason.detail === 'string' ? reason.detail : reason instanceof Error ? reason.message : '删除失败，请重试') }
}
void load()
onUnmounted(() => { alive = false; ++sequence; ++detailSequence; clearTimeout(timer); clearTimeout(poll); overseasImageCache.clear() })
</script>
<style src="@/views/shared/studio/studio.css"></style>
<style src="./library.css"></style>
