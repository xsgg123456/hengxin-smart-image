<template>
  <ElDialog :model-value="true" :title="batch ? `批量标注 · ${pictures.length}张图片` : `修改这张 · ${current.name}`" :width="batch ? 'min(1640px,98vw)' : 'min(1380px,96vw)'" align-center append-to-body class="batch-editor-dialog" :close-on-click-modal="false" :show-close="!locked" :close-on-press-escape="!locked" @update:model-value="!$event && close()">
    <div v-if="batch" class="batch-context"><span>逐张标注，只带回有标注的图片</span><div><ElButton v-if="focused" size="small" :disabled="locked" @click="focused = false">← 返回整组画布</ElButton><span>已标注 <strong>{{ marked.length }}</strong> / {{ pictures.length }} 张</span></div></div>
    <div class="batch-editor-layout">
      <div class="batch-picture-area">
        <BatchBoard v-if="batch && !focused" :pictures="pictures" :key-for="keyFor" :selected="active" :selected-mark="selected" :disabled="locked" @select="select" @focus="id => { select(id); focused = true }" @mark="selected = $event" />
        <template v-else>
          <div v-if="batch" class="focus-navigation"><ElButton size="small" :disabled="locked || activeIndex === 0" @click="select(pictures[activeIndex - 1].id)">上一张</ElButton><span>{{ current.name }} · {{ activeIndex + 1 }}/{{ pictures.length }}</span><ElButton size="small" :disabled="locked || activeIndex === pictures.length - 1" @click="select(pictures[activeIndex + 1].id)">下一张</ElButton></div>
          <ElAlert v-if="loadError" :title="loadError" type="error" :closable="false"><ElButton text @click="loadImage">重试读取图片</ElButton></ElAlert>
          <div v-else-if="!imageReady" class="editor-loading">正在读取原图…</div>
          <AnnotationCanvas v-else :key="current.id" v-model="draft.marks" :image-url="originalUrl" :width="originalWidth" :height="originalHeight" :disabled="locked" :selected-id="selected" @select="selected = $event" />
          <p class="hx-footnote">成品原始尺寸：{{ current.width }} × {{ current.height }} · 当前图片：{{ current.name }}</p>
        </template>
      </div>
      <aside class="batch-notes" :aria-label="`${current.name}修改内容`">
        <div class="notes-heading"><strong>{{ current.name }}</strong><small>当前修改图片</small></div>
        <h3>问题位置与修改意见 · {{ draft.marks.length }}处</h3>
        <p class="hx-footnote">在左侧圈出问题，逐处填写描述。整体要求回到工作台输入区补充。</p>
        <ElEmpty v-if="!draft.marks.length" description="暂无标注，在左侧圈出需要修改的位置" :image-size="62" />
        <div v-for="(mark, i) in draft.marks" :key="mark.id" class="mark-note" :class="{ selected: selected === mark.id }" @click="selected = mark.id">
          <div><label :for="`mark-${mark.id}`">标注{{ i + 1 }} · {{ mark.kind === 'rect' ? '框选' : '画笔' }}</label><ElButton text size="small" :disabled="locked" :aria-label="`删除标注${i + 1}`" @click.stop="draft.marks = draft.marks.filter(m => m.id !== mark.id)">删除</ElButton></div>
          <ElInput :id="`mark-${mark.id}`" v-model="mark.note" :aria-label="`标注${i + 1}修改意见`" type="textarea" :rows="2" maxlength="4000" placeholder="这里需要改成什么？" :disabled="locked" />
        </div>
        <ReferencePanel :key="current.id" :draft="draft" :disabled="locked" />
        <ElAlert v-if="batch && !draft.marks.length && draft.references.length" title="当前图片只有参考图，尚未标注，本次不会带回；草稿仍保留。" type="warning" :closable="false" />
        <p class="hx-footnote">关闭会保留本页草稿，确认后回到工作台再发送。</p>
        <ElButton v-if="draft.marks.length || draft.references.length" text type="danger" :disabled="locked" @click="clear">清空当前图片的修改草稿</ElButton>
      </aside>
    </div>
    <ElAlert v-if="localError || error" :title="localError || error" type="error" :closable="false" class="editor-error" />
    <template #footer><div class="editor-footer"><span>确认后回到输入区，由你补充并发送</span><div><ElButton :disabled="locked" @click="close">关闭并保留草稿</ElButton><ElButton type="primary" :disabled="locked || (batch && !marked.length && !hasConfirmed)" :loading="preparing || submitting" @click="prepare">{{ batch ? `确认并带回工作台（${marked.length}张）` : '确认标注' }}</ElButton></div></div></template>
  </ElDialog>
  <ElDialog v-model="reviewOpen" title="确认本次修改内容" width="min(980px,94vw)" align-center append-to-body class="batch-review-dialog" :close-on-click-modal="false" :show-close="!submitting" :close-on-press-escape="!submitting" :before-close="reviewClose">
    <ElAlert :title="batch && !prepared.length && hasConfirmed ? '本组已清空，确认将移除工作台中本组待发送修改' : `本次带回${prepared.length}张图片，不会自动发送或生成`" type="info" :closable="false" />
    <p v-if="excludedReferences.length" class="hx-footnote">{{ excludedReferences.join('、') }}只有参考图、没有标注，本次不带回；草稿保留。</p>
    <RevisionDetails :items="prepared" /><ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><ElButton :disabled="submitting" @click="reviewClose">返回继续编辑</ElButton><ElButton type="primary" :loading="submitting" :disabled="submitting" @click="confirm">确认并带回输入区</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import type { StudioPicture } from '@/api/shared/studio'
import AnnotationCanvas from '@/views/hengxin/components/annotation/AnnotationCanvas.vue'
import { loadStudioImage } from '../studio-images'
import BatchBoard from './BatchBoard.vue'
import ReferencePanel from './ReferencePanel.vue'
import RevisionDetails from './RevisionDetails.vue'
import { clearDraft, decodeImage, disposePrepared, draftFor, snapshot, validateDraft, type PreparedRevision } from './state'
import './style.css'
const props = defineProps<{ pictures: StudioPicture[]; initialId: string; batch: boolean; keyFor: (p: StudioPicture) => string; submitting: boolean; error?: string; hasConfirmed?: boolean }>()
const emit = defineEmits<{ close: []; confirm: [items: PreparedRevision[], groupIds?: string[]] }>()
const active = ref(props.initialId), selected = ref(''), focused = ref(false), preparing = ref(false), reviewOpen = ref(false), localError = ref(''), prepared = ref<PreparedRevision[]>([])
const current = computed(() => props.pictures.find(p => p.id === active.value) || props.pictures[0])
const activeIndex = computed(() => props.pictures.indexOf(current.value)), draft = computed(() => draftFor(props.keyFor(current.value)))
const marked = computed(() => props.pictures.filter(p => draftFor(props.keyFor(p)).marks.length))
const locked = computed(() => preparing.value || reviewOpen.value || props.submitting)
const excludedReferences = computed(() => props.batch ? props.pictures.filter(p => !draftFor(props.keyFor(p)).marks.length && draftFor(props.keyFor(p)).references.length).map(p => p.name) : [])
const imageReady = ref(false), loadError = ref(''), originalUrl = ref(''), originalWidth = ref(0), originalHeight = ref(0)
let loadEpoch = 0, loadController = new AbortController(), alive = true
const preparationController = new AbortController()
async function loadImage() {
  const epoch = ++loadEpoch; loadController.abort(); loadController = new AbortController()
  imageReady.value = false; loadError.value = ''; URL.revokeObjectURL(originalUrl.value); originalUrl.value = ''
  try {
    const result = await decodeImage(await loadStudioImage(current.value, loadController.signal))
    if (epoch !== loadEpoch || !alive) { URL.revokeObjectURL(result.url); return }
    originalUrl.value = result.url; originalWidth.value = result.image.naturalWidth; originalHeight.value = result.image.naturalHeight; imageReady.value = true
  } catch (error) { if (epoch === loadEpoch && alive) loadError.value = error instanceof Error ? error.message : '原图读取失败，请重试' }
}
watch(() => props.keyFor(current.value), loadImage, { immediate: true })
function select(id: string) { if (!locked.value) { active.value = id; selected.value = ''; localError.value = '' } }
function close() { if (!locked.value) emit('close') }
function reviewClose() { if (props.submitting) return; reviewOpen.value = false; disposePrepared(prepared.value); prepared.value = [] }
async function clear() {
  if (locked.value) return
  const target = draft.value
  try { await ElMessageBox.confirm('将清空当前图片的标注和参考图，其他图片不受影响。', '清空当前草稿', { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  if (alive && !locked.value) { clearDraft(target); localError.value = ''; selected.value = '' }
}
async function prepare() {
  if (locked.value || (props.batch && !marked.value.length && !props.hasConfirmed)) return
  localError.value = ''; const targets = props.batch ? marked.value : [current.value]
  for (const p of targets) { const message = validateDraft(draftFor(props.keyFor(p))); if (message) { select(p.id); localError.value = `${p.name}：${message}`; return } }
  preparing.value = true
  const items: PreparedRevision[] = []
  try {
    for (const picture of targets) items.push(await snapshot(picture, props.keyFor(picture), preparationController.signal))
    if (!alive) { disposePrepared(items); return }
    disposePrepared(prepared.value); prepared.value = items; reviewOpen.value = true
  } catch (error) { disposePrepared(items); if (alive) localError.value = error instanceof Error ? error.message : '准备修改材料失败，请重试' }
  finally { preparing.value = false }
}
function confirm() { if (!props.submitting) emit('confirm', prepared.value, props.batch ? props.pictures.map(p => p.id) : undefined) }
onBeforeUnmount(() => { alive = false; ++loadEpoch; loadController.abort(); preparationController.abort(); URL.revokeObjectURL(originalUrl.value); disposePrepared(prepared.value) })
</script>
