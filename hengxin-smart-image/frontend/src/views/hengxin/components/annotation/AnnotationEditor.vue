<template>
  <div class="annotation-editor">
    <section class="picture-area" v-loading="loading">
      <ElAlert v-if="loadError" :title="loadError" type="error" :closable="false"><ElButton text @click="load">重新读取成品原图</ElButton></ElAlert>
      <AnnotationCanvas v-if="original" v-model="draft.marks" :image-url="originalUrl" :width="original.naturalWidth" :height="original.naturalHeight" :disabled="disabled || draft.mode !== 'direct' || previewOpen" :selected-id="selected" @select="selected = $event" />
      <p class="hx-footnote">{{ original ? `成品原始尺寸：${original.naturalWidth} × ${original.naturalHeight}` : '正在读取所选版本的成品原始文件' }} · {{ baseLabel }}</p>
    </section>
    <aside>
      <ElRadioGroup v-model="draft.mode" :disabled="disabled || previewOpen"><ElRadioButton value="direct">直接标注</ElRadioButton><ElRadioButton value="upload">上传已有标注图</ElRadioButton></ElRadioGroup>
      <template v-if="draft.mode === 'direct'">
        <h3>问题位置与修改意见 · {{ draft.marks.length }} 处</h3>
        <p class="hx-footnote">先框选或用画笔圈出位置，再填写修改意见。</p>
        <div class="mark-notes"><ElEmpty v-if="!draft.marks.length" description="从左侧框选或圈注第一处问题" :image-size="60" />
          <div v-for="(mark, i) in draft.marks" :key="mark.id" class="mark-note" :class="{ selected: selected === mark.id }" @click="selected = mark.id">
            <label :for="`mark-${mark.id}`">标注 {{ i + 1 }} · {{ mark.kind === 'rect' ? '框选' : '画笔' }}</label>
            <ElInput :id="`mark-${mark.id}`" v-model="mark.note" :aria-label="`标注 ${i + 1} 修改意见`" type="textarea" :rows="2" :maxlength="limit" :disabled="disabled || previewOpen" placeholder="这里需要改成什么？" />
          </div>
        </div>
      </template>
      <UploadInteraction v-else :disabled="disabled || previewOpen" @files="receive" @error="localError = $event">
        <input ref="picker" type="file" accept="image/jpeg,image/png" hidden @change="pick" />
        <button v-if="!draft.uploaded" class="upload-box" :disabled="disabled" @click="picker?.click()">上传已有标注图，或拖到这里<br />JPG / PNG · 最多 1 张 · 10 MiB</button>
        <template v-else><ElImage class="uploaded" :src="uploadUrl" fit="contain" /><ElButton text type="danger" :disabled="disabled" @click="draft.uploaded = undefined">移除标注图</ElButton></template>
      </UploadInteraction>
      <label class="general-label">{{ requireText && (draft.mode === 'upload' || !draft.marks.length) ? '修改意见（必填）' : '整体补充要求（可选）' }}</label><ElInput v-model="draft.general" aria-label="整体补充要求" type="textarea" :rows="3" :maxlength="limit" show-word-limit :disabled="disabled || previewOpen" placeholder="例如：保持其他设计、文字和布局不变。" />
      <ElAlert class="annotation-info" title="只修改这张图片" description="系统自动附带本次修改需要的原图与素材。标注框、笔迹和编号只用于定位，不作为成品内容。" type="info" :closable="false" />
      <ElAlert v-if="localError" :title="localError" type="error" :closable="false" />
    </aside>
  </div>
  <ElDialog v-model="previewOpen" title="确认本次修改内容" width="min(1000px, 94vw)" append-to-body align-center :close-on-click-modal="false" :show-close="!disabled" :close-on-press-escape="!disabled">
    <div class="confirmation"><ElImage :src="previewUrl || originalUrl" fit="contain" /><div><strong>{{ baseLabel }} · 无标注成品为修改基础</strong><p class="hx-footnote">标注仅用于定位，不承诺框外像素逐一不变。</p><pre>{{ prepared?.text || '根据上传标注图定位修改' }}</pre></div></div>
    <template #footer><ElButton :disabled="disabled" @click="previewOpen = false">返回继续标注</ElButton><ElButton type="primary" :loading="disabled" @click="confirm">确认提交修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import AnnotationCanvas from './AnnotationCanvas.vue'
import UploadInteraction from '../UploadInteraction.vue'
import { annotationDraft, annotationText } from './annotation-drafts'
import { exportAnnotation } from './annotation-export'
const props = defineProps<{ draftKey: string; loadOriginal: () => Promise<Blob>; baseLabel: string; limit: number; disabled?: boolean; requireText?: boolean }>()
export interface PreparedAnnotation { text: string; file?: File }
const emit = defineEmits<{ submit: [value: PreparedAnnotation] }>()
const draft = computed(() => annotationDraft(props.draftKey))
const selected = ref(''), original = shallowRef<HTMLImageElement>(), originalUrl = ref(''), loadError = ref(''), loading = ref(false)
const localError = ref(''), picker = ref<HTMLInputElement>(), uploadUrl = ref(''), previewUrl = ref(''), previewOpen = ref(false), preparing = ref(false)
const prepared = shallowRef<PreparedAnnotation>()
let generation = 0
function revoke(url: string) { if (url) URL.revokeObjectURL(url) }
async function load() {
  const token = ++generation; loading.value = true; loadError.value = ''; original.value = undefined; revoke(originalUrl.value); originalUrl.value = ''
  let url = ''
  try {
    const blob = await props.loadOriginal()
    if (!blob.size || !blob.type.startsWith('image/')) throw new Error('成品原始文件不可用')
    url = URL.createObjectURL(blob); const image = new Image(); image.src = url; await image.decode()
    if (!image.naturalWidth || !image.naturalHeight) throw new Error('成品原图无法解码')
    if (token !== generation) return
    original.value = image; originalUrl.value = url; url = ''
  } catch (error) { if (token === generation) loadError.value = error instanceof Error ? error.message : '原图读取失败' }
  finally { revoke(url); if (token === generation) loading.value = false }
}
watch(() => props.draftKey, () => { previewOpen.value = false; selected.value = ''; localError.value = ''; void load() }, { immediate: true })
watch(() => draft.value.uploaded, file => { revoke(uploadUrl.value); uploadUrl.value = file ? URL.createObjectURL(file) : '' }, { immediate: true })
async function receive(files: File[]) {
  if (props.disabled || previewOpen.value) return
  localError.value = ''
  if (files.length !== 1 || draft.value.uploaded) { localError.value = '最多上传一张标注图，请先移除已有图片'; return }
  const file = files[0], token = generation
  if (!['image/jpeg', 'image/png'].includes(file.type) || !/\.(png|jpe?g)$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) { localError.value = '请选择不超过 10 MiB 的 JPG / PNG 图片'; return }
  const url = URL.createObjectURL(file)
  try {
    const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer())
    const valid = file.type === 'image/png' ? [137,80,78,71,13,10,26,10].every((b, i) => bytes[i] === b) : bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
    if (!valid) throw new Error('图片内容与格式不符')
    const image = new Image(); image.src = url; await image.decode()
    if (token === generation && !props.disabled && !draft.value.uploaded) draft.value.uploaded = file
  } catch { if (token === generation) localError.value = '图片无法读取，请选择有效图片' }
  finally { revoke(url) }
}
function pick(event: Event) { const input = event.target as HTMLInputElement; void receive(Array.from(input.files ?? [])); input.value = '' }
async function preview() {
  if (props.disabled || preparing.value) return
  localError.value = ''; preparing.value = true; const token = generation
  try {
    if (!original.value) throw new Error('请等待成品原图读取成功后再提交')
    const text = annotationText(draft.value, props.limit, !props.requireText)
    const file = draft.value.mode === 'upload' ? draft.value.uploaded : draft.value.marks.length ? await exportAnnotation(original.value, draft.value.marks) : undefined
    if (token !== generation || props.disabled) return
    prepared.value = { text, file }; revoke(previewUrl.value); previewUrl.value = file ? URL.createObjectURL(file) : ''; previewOpen.value = true
  } catch (error) { localError.value = error instanceof Error ? error.message : '生成标注预览失败' }
  finally { preparing.value = false }
}
function confirm() { if (prepared.value && !props.disabled) { previewOpen.value = false; emit('submit', prepared.value) } }
onBeforeUnmount(() => { generation++; revoke(originalUrl.value); revoke(uploadUrl.value); revoke(previewUrl.value) })
defineExpose({ preview })
</script>
<style scoped>
.annotation-editor { display:grid; grid-template-columns:minmax(0, 2.65fr) minmax(280px,1fr); gap:24px; max-height:70vh; overflow:auto; }
.picture-area, aside { min-width:0; } .picture-area { min-height:300px; }
h3 { font-size:14px; margin:22px 0 8px; } .mark-notes { max-height:30vh; overflow:auto; }
.mark-note { padding:10px; border:1px solid var(--el-border-color); border-radius:8px; margin-bottom:8px; } .mark-note.selected { border-color:#c35a28; }
.mark-note label { display:block; margin-bottom:8px; color:#b54b1d; } .general-label { display:block; margin:20px 0 8px; }
.annotation-info { margin:20px 0 12px; } .upload-box { width:100%; padding:30px 10px; margin-top:20px; border:1px dashed var(--el-border-color); border-radius:8px; background:transparent; color:inherit; cursor:pointer; }
.uploaded { width:100%; height:180px; } .confirmation { display:grid; grid-template-columns:1fr 1fr; gap:24px; max-height:65vh; overflow:auto; } .confirmation .el-image { max-height:60vh; } pre { white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; }
@media(max-width:900px) { .annotation-editor,.confirmation { grid-template-columns:1fr; } .mark-notes { max-height:250px; } }
</style>
