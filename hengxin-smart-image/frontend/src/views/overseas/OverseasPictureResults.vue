<template>
  <ElCard class="art-card hx-section hx-gap pictures-panel" shadow="never">
    <div class="hx-section-title"><h2>图片审核</h2><ElButton :disabled="saving || !!pending" :loading="loading" @click="load()">刷新图片</ElButton></div>
    <p v-if="loading" role="status">正在加载图片…</p><ElAlert v-if="error" :title="error" type="warning" :closable="false" />
    <ElEmpty v-if="loaded && !items.length" description="暂无生成图片" />
    <p v-if="!allowed" class="hx-footnote">当前为只读视角，图片处理需由负责设计或设计主管操作。</p>
    <ElTabs v-if="items.length" v-model="sku"><ElTabPane v-for="code in skus" :key="code" :name="code" :label="code" /></ElTabs>
    <div class="hx-result-grid">
      <ElCard v-for="picture in visible" :key="picture.id" shadow="never">
        <ElImage v-if="picture.url" :src="picture.url" :alt="picture.title" fit="contain" :preview-src-list="[picture.url]" preview-teleported><template #error>图片加载失败，请刷新重试</template></ElImage>
        <ElEmpty v-else description="尚无生成产物" :image-size="60" />
        <div class="hx-result-meta"><strong>{{ picture.title }} · v{{ picture.version }}</strong></div>
        <ElTag :type="picture.approved ? 'success' : 'info'">{{ labels[picture.status] }}{{ picture.approved ? ' · 已通过' : '' }}</ElTag>
        <div class="actions">
          <ElButton v-if="picture.url" text @click="download(picture.id, picture.version)">下载原图</ElButton>
          <ElButton v-if="allowed && !archived" text type="primary" :disabled="locked || picture.status !== 'ready' || picture.approved" @click="start('approve', picture)">审核通过</ElButton>
          <ElButton v-if="allowed && !archived && picture.url" text :disabled="locked || !['ready', 'failed'].includes(picture.status)" @click="editing = picture; conflict = false">标注修改</ElButton>
        </div>
        <details v-if="picture.history.length"><summary>版本历史</summary><div v-for="h in picture.history" :key="h.version" class="hx-gap"><p class="hx-footnote">v{{ h.version }} · {{ h.createdAt }} · {{ h.note || '初次生成' }}</p><ElImage :src="h.url" :alt="`历史 v${h.version}`" fit="contain" :preview-src-list="[h.url]" preview-teleported /><ElButton text @click="download(picture.id, h.version)">下载 v{{ h.version }}</ElButton></div></details>
      </ElCard>
    </div>
    <div v-if="allowed && !archived" class="actions hx-gap"><ElButton v-for="code in failedSkus" :key="code" :disabled="locked" @click="start('retry', undefined, code)">重试失败 SKU {{ code }}</ElButton><ElButton type="primary" :disabled="locked || !canArchive(items, task.status)" @click="start('archive')">整套归档到成品库</ElButton></div>
    <ElButton v-if="pending && !editing" class="hx-gap" :loading="saving" :disabled="!allowed" @click="send">核实并重试图片原请求</ElButton>
    <OverseasPictureAnnotation v-if="editing" :key="editing.id" :picture="editing" :allowed="allowed" :locked="saving || !!pending" :conflict="conflict" :failure="error" :retryable="!!pending && !saving" @retry="send" @close="editing = undefined" @submit="revise" />
  </ElCard>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { canArchive, createPicturesApi, saveBlob, pictureFilename, type Picture, type PictureCommand } from '@/api/overseas/pictures'
import { createRequestKeys, taskError, type TaskDetail } from '@/api/overseas/tasks'
import { cloneMarks, type AnnotationMark } from '../hengxin/components/annotation/annotation-model'
import OverseasPictureAnnotation from './OverseasPictureAnnotation.vue'
const props = defineProps<{ task: TaskDetail; refresh: number }>()
const emit = defineEmits<{ changed: [task: TaskDetail]; refresh: []; failure: [reason: unknown] }>()
const api = createPicturesApi(), keys = createRequestKeys(), items = ref<Picture[]>([]), sku = ref(''), error = ref(''), taskVersion = ref(0)
const loading = ref(false), loaded = ref(false), saving = ref(false), editing = ref<Picture>(), conflict = ref(false), pending = ref<{ body: PictureCommand; key: string }>()
const labels = { pending: '等待生成', ready: '待审核', reworking: '返工中', failed: '生成失败' }
const allowed = computed(() => props.task.capabilities.includes('task.design')), archived = computed(() => props.task.status === 'archived')
const locked = computed(() => loading.value || saving.value || !!pending.value)
const skus = computed(() => [...new Set(items.value.map(p => p.sku))]), visible = computed(() => items.value.filter(p => p.sku === sku.value))
const failedSkus = computed(() => [...new Set(items.value.filter(p => p.status === 'failed' && !p.version).map(p => p.sku))])
let epoch = 0, alive = true
function fail(reason: unknown) {
  error.value = taskError(reason)
  if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) { ++epoch; items.value = []; editing.value = undefined; pending.value = undefined; keys.clear(); emit('failure', reason) }
}
async function load(preserve = false) {
  const current = ++epoch; loading.value = true; if (!preserve) error.value = ''
  try { const value = await api.list(props.task.id); if (!alive || current !== epoch) return; items.value = value.items; taskVersion.value = value.taskVersion; loaded.value = true; if (!skus.value.includes(sku.value)) sku.value = skus.value[0] || ''; if (editing.value && !items.value.some(p => p.id === editing.value?.id && p.version === editing.value?.version && ['ready', 'failed'].includes(p.status))) conflict.value = true }
  catch (reason) { if (alive && current === epoch) { items.value = []; loaded.value = false; fail(reason) } }
  finally { if (current === epoch) loading.value = false }
}
function start(kind: PictureCommand['kind'], picture?: Picture, code = '', note = '', marks: AnnotationMark[] = []) {
  if (!allowed.value || archived.value || locked.value) return
  const body: PictureCommand = { kind, taskId: props.task.id, pictureId: picture?.id || '', version: picture?.version || 0, taskVersion: taskVersion.value, sku: code, note, marks: cloneMarks(marks) }
  pending.value = { body, key: keys.for(body) }; void send()
}
function revise(version: number, note: string, marks: AnnotationMark[]) { if (editing.value?.version === version && !conflict.value) start('revision', editing.value, '', note, marks) }
async function send() {
  const request = pending.value, current = epoch
  if (!request || saving.value || !allowed.value) return
  saving.value = true; error.value = ''
  try { const value = await api.command(request.body, request.key); if (!alive || current !== epoch || !allowed.value) return; pending.value = undefined; editing.value = undefined; keys.clear(); emit('changed', value); await load(); emit('refresh') }
  catch (reason) {
    if (!alive || current !== epoch || !allowed.value) return
    if (reason instanceof IdentityError && reason.status > 0 && reason.status < 500) { pending.value = undefined; if (reason.status === 409) { await load(); emit('refresh') }; fail(reason) }
    else error.value = '请求结果尚未确认，请核实并重试图片原请求；完整意见已保留。'
  } finally { saving.value = false }
}
async function download(id: string, version: number) { try { const blob = await api.content(id, version); if (alive) saveBlob(blob, pictureFilename(id, version, blob.type)) } catch (reason) { if (alive) fail(reason) } }
watch(() => props.task.id, () => { editing.value = undefined; pending.value = undefined; keys.clear(); void load() }, { immediate: true })
watch([() => props.task.version, () => props.refresh], () => { if (!saving.value && !pending.value) void load(true) })
watch(allowed, value => { if (!value) { ++epoch; editing.value = undefined; pending.value = undefined; keys.clear(); void load() } })
onUnmounted(() => { alive = false; ++epoch; editing.value = undefined; pending.value = undefined; items.value = [] })
</script>
<style scoped>
.pictures-panel { min-width: 0; overflow-wrap: anywhere; }
.hx-result-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.hx-section-title, .actions { display: flex; flex-wrap: wrap; gap: 8px; }
.actions .el-button { margin-left: 0; }
h2 { font-size: 16px; }
@media (max-width: 600px) { .hx-result-grid { grid-template-columns: 1fr; } }
</style>
