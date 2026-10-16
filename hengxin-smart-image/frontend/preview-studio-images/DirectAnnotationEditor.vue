<template>
  <div class="annotation-editor">
    <section class="picture-area" v-loading="loading">
      <ElAlert v-if="loadError" :title="loadError" type="error" :closable="false"><ElButton text @click="load">重新读取原图</ElButton></ElAlert>
      <AnnotationCanvas v-if="original" v-model="draft.marks" :image-url="originalUrl" :width="original.naturalWidth" :height="original.naturalHeight" :disabled="previewOpen" :selected-id="selected" @select="selected = $event" />
      <p class="hx-footnote">{{ original ? `成品原始尺寸：${original.naturalWidth} × ${original.naturalHeight}` : '正在读取原图' }} · {{ baseLabel }}</p>
    </section>
    <aside>
      <h3>问题位置与修改意见 · {{ draft.marks.length }} 处</h3>
      <p class="hx-footnote">在左侧圈出问题，逐处填写描述。整体要求回到工作台输入区补充。</p>
      <div class="mark-notes"><ElEmpty v-if="!draft.marks.length" description="暂无标注；也可带回原图，在工作台填写修改要求" :image-size="60" />
        <div v-for="(mark, i) in draft.marks" :key="mark.id" class="mark-note" :class="{ selected: selected === mark.id }" @click="selected = mark.id">
          <label :for="`mark-${mark.id}`">标注 {{ i + 1 }} · {{ mark.kind === 'rect' ? '框选' : '画笔' }}</label>
          <ElInput :id="`mark-${mark.id}`" v-model="mark.note" :aria-label="`标注 ${i + 1} 修改意见`" type="textarea" :rows="2" :maxlength="4000" :disabled="previewOpen" placeholder="这里需要改成什么？" />
        </div>
      </div>
      <ElAlert class="annotation-info" title="只修改这张图片" description="标注仅用于说明修改位置。确认后回到工作台输入区，你可以继续补充，再点击发送。" type="info" :closable="false" />
      <ElAlert v-if="localError" :title="localError" type="error" :closable="false" />
    </aside>
  </div>
  <ElDialog v-model="previewOpen" title="确认本次修改内容" width="min(1000px,94vw)" append-to-body align-center :close-on-click-modal="false">
    <div class="confirmation"><div class="annotation-inputs"><div><img :src="originalUrl" alt="无标注原图"><small>原图 · 修改基础</small></div><div v-if="previewUrl"><img :src="previewUrl" alt="本轮标注图"><small>标注图 · 问题定位</small></div></div><div><strong>{{ baseLabel }} · 无标注成品为修改基础</strong><p class="hx-footnote">标注仅用于定位，修改意见确认后带回输入区。</p><pre>{{ prepared?.text || '未添加位置标注，请回到工作台输入区填写修改要求。' }}</pre></div></div>
    <template #footer><ElButton @click="previewOpen = false">返回继续标注</ElButton><ElButton type="primary" @click="confirm">确认并带回输入区</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import AnnotationCanvas from '@/views/hengxin/components/annotation/AnnotationCanvas.vue'
import { annotationDraft, annotationText } from '@/views/hengxin/components/annotation/annotation-drafts'
import { exportAnnotation } from '@/views/hengxin/components/annotation/annotation-export'
import type { PreparedAnnotation } from '@/views/hengxin/components/annotation/AnnotationEditor.vue'
const props = defineProps<{ draftKey: string; loadOriginal: () => Promise<Blob>; baseLabel: string }>()
const emit = defineEmits<{ submit: [value: PreparedAnnotation]; previewState: [locked: boolean] }>()
const draft = computed(() => annotationDraft(props.draftKey))
const selected = ref(''), original = shallowRef<HTMLImageElement>(), originalUrl = ref(''), loadError = ref(''), loading = ref(false)
const localError = ref(''), previewUrl = ref(''), previewOpen = ref(false), preparing = ref(false)
const prepared = shallowRef<PreparedAnnotation>()
watch([preparing, previewOpen], () => emit('previewState', preparing.value || previewOpen.value), { flush: 'sync' })
let generation = 0
function revoke(url: string) { if (url) URL.revokeObjectURL(url) }
async function load() {
  const token = ++generation; loading.value = true; loadError.value = ''; original.value = undefined; revoke(originalUrl.value); originalUrl.value = ''
  let url = ''
  try {
    const blob = await props.loadOriginal()
    if (!blob.size || !blob.type.startsWith('image/')) throw new Error('原始图片不可用')
    url = URL.createObjectURL(blob); const image = new Image(); image.src = url; await image.decode()
    if (!image.naturalWidth || !image.naturalHeight) throw new Error('原图无法解码')
    if (token !== generation) return
    original.value = image; originalUrl.value = url; url = ''
  } catch (error) { if (token === generation) loadError.value = error instanceof Error ? error.message : '原图读取失败' }
  finally { revoke(url); if (token === generation) loading.value = false }
}
watch(() => props.draftKey, () => {
  // 清除预览旧版上传与整体意见，保留逐处标注草稿。
  draft.value.mode = 'direct'; draft.value.uploaded = undefined; draft.value.general = ''
  previewOpen.value = false; selected.value = ''; localError.value = ''; void load()
}, { immediate: true })
async function preview() {
  if (preparing.value) return
  localError.value = ''; preparing.value = true; const token = generation
  try {
    if (!original.value) throw new Error('请等待原图读取成功后再确认')
    const text = draft.value.marks.length ? annotationText({ ...draft.value, mode: 'direct', general: '' }, 4000, false) : ''
    const file = draft.value.marks.length ? await exportAnnotation(original.value, draft.value.marks) : undefined
    if (token !== generation) return
    prepared.value = { text, file }; revoke(previewUrl.value); previewUrl.value = file ? URL.createObjectURL(file) : ''; previewOpen.value = true
  } catch (error) { localError.value = error instanceof Error ? error.message : '生成标注预览失败' }
  finally { preparing.value = false }
}
function confirm() { if (prepared.value) { previewOpen.value = false; emit('submit', prepared.value) } }
onBeforeUnmount(() => { generation++; emit('previewState', false); revoke(originalUrl.value); revoke(previewUrl.value) })
defineExpose({ preview })
</script>
<style scoped>
.annotation-editor{display:grid;grid-template-columns:minmax(0,2.65fr) minmax(280px,1fr);gap:24px;height:min(70dvh,760px);overflow:hidden;grid-template-rows:minmax(0,1fr)}
.picture-area,aside{min-width:0;min-height:0}.picture-area{display:flex;flex-direction:column}.picture-area>.annotation-canvas{flex:1;height:auto}aside{overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding-right:4px}
h3{font-size:14px;margin:0 0 8px}.mark-notes{min-height:0}.mark-note{padding:10px;border:1px solid var(--el-border-color);border-radius:8px;margin-bottom:8px}.mark-note.selected{border-color:var(--el-color-primary)}.mark-note label{display:block;margin-bottom:8px;color:var(--el-color-primary)}.annotation-info{margin:20px 0 12px}
.confirmation{display:grid;grid-template-columns:1fr 1fr;gap:24px;max-height:65vh;overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
@media(max-width:900px){.annotation-editor{grid-template-columns:1fr;grid-template-rows:minmax(230px,1fr) 150px;gap:12px;height:calc(100dvh - 200px);min-height:400px}.confirmation{grid-template-columns:1fr}}
</style>
