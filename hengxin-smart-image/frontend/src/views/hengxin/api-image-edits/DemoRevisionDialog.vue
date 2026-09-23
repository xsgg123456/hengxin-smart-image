<template>
  <ElDialog v-model="open" title="修改这张结果" width="min(900px, 94vw)" append-to-body :close-on-click-modal="false">
    <div v-if="item?.result" class="revision-layout">
      <section><h3>当前生成结果 · 原图 {{ index + 1 }} · V{{ item.result.version || 1 }}</h3><div class="current-picture"><PicturePreview :picture="item.result" title="本次修改基于当前结果" /></div><p class="hx-footnote">以当前 V{{ item.result.version || 1 }} 为基础修改；成功后新增版本并设为当前，历史图片保留。</p></section>
      <section>
        <ElForm label-position="top">
          <ElFormItem label="修改说明"><ElInput v-model="text" aria-label="修改说明" type="textarea" :rows="6" maxlength="4000" show-word-limit placeholder="写下需要调整的地方，也可以只上传标注图。" :disabled="busy" /></ElFormItem>
          <ElFormItem label="标注图（可选，最多 1 张）">
            <UploadInteraction class="annotation-control" :disabled="!open || busy || reading" @files="receiveAnnotation" @error="error = $event">
              <input ref="picker" class="file-input" type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" aria-label="上传修改标注图" :disabled="!open || busy || reading" @change="readAnnotation" />
              <div v-if="annotation" class="annotation-preview"><PicturePreview :picture="annotation" title="修改标注图" /><ElButton text type="danger" :disabled="busy || reading" @click="annotation = undefined">移除标注图</ElButton></div>
              <button v-else type="button" class="annotation-drop" :disabled="busy || reading" @click="picker?.click()"><strong>选择 JPG / PNG 标注图，或拖到这里</strong></button>
              <p class="hx-footnote">单张不超过 10 MiB。图片与说明仅用于本地交互预览。</p>
            </UploadInteraction>
          </ElFormItem>
          <ElFormItem label="模拟修改结果 · 仅预览"><ElSelect v-model="scenario" aria-label="模拟修改结果" :disabled="busy"><ElOption label="修改成功" value="success" /><ElOption label="重试耗尽后失败" value="partial" /></ElSelect></ElFormItem>
        </ElForm>
        <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <p v-else class="hx-footnote">修改说明与标注图至少填写一种。</p>
      </section>
    </div>
    <template #footer><ElButton @click="open = false">取消</ElButton><ElButton type="primary" :loading="busy" :disabled="reading || (!text.trim() && !annotation)" @click="submit">提交单图修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Picture } from '@/types/hengxin'
import PicturePreview from '../components/PicturePreview.vue'
import UploadInteraction from '../components/UploadInteraction.vue'
import { singleImageError } from '../components/upload-interaction'
import { requestRevision, type EditTask, type Scenario } from './preview-state'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: EditTask; index: number }>()
const item = computed(() => props.task.items[props.index])
const text = ref(''), annotation = ref<Picture>(), scenario = ref<Scenario>('success')
const error = ref(''), busy = ref(false), reading = ref(false), picker = ref<HTMLInputElement>()
let readToken = 0
onBeforeUnmount(() => { readToken++ })
watch(open, value => { readToken++; reading.value = false; if (value) { text.value = ''; annotation.value = undefined; scenario.value = 'success'; error.value = ''; busy.value = false } })
async function readAnnotation(event: Event) {
  const input = event.target as HTMLInputElement, files = Array.from(input.files ?? []); input.value = ''
  await receiveAnnotation(files)
}
async function receiveAnnotation(files: File[]) {
  if (!open.value || busy.value || reading.value) return
  const reason = singleImageError(files.length, !!annotation.value)
  if (reason) { error.value = reason; return }
  const file = files[0]
  if (!file) return
  error.value = ''
  if (!['image/jpeg', 'image/png'].includes(file.type) || !/\.(jpe?g|png)$/i.test(file.name)) { error.value = '请选择 JPG 或 PNG 图片'; return }
  if (!file.size || file.size > 10 * 1024 * 1024) { error.value = '标注图不能为空或超过 10 MiB'; return }
  const token = ++readToken; reading.value = true
  try {
    const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer())
    const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
    const png = [137, 80, 78, 71, 13, 10, 26, 10].every((byte, index) => bytes[index] === byte)
    if ((file.type === 'image/jpeg' && !jpeg) || (file.type === 'image/png' && !png)) throw new Error('图片内容与格式不符，请选择有效的 JPG / PNG')
    const url = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error('读取图片失败，请重新选择')); reader.readAsDataURL(file) })
    const image = new Image(); image.src = url; await image.decode()
    if (!image.naturalWidth || !image.naturalHeight) throw new Error('图片无法解码，请重新选择')
    if (token === readToken && open.value) annotation.value = { name: file.name, url }
  } catch (reason) { if (token === readToken) error.value = reason instanceof Error ? reason.message : '图片读取失败，请重新选择' }
  finally { if (token === readToken) reading.value = false }
}
async function submit() {
  if (busy.value || reading.value || (!text.value.trim() && !annotation.value)) return
  busy.value = true; error.value = ''
  try { requestRevision(props.task, props.index, text.value.trim(), annotation.value, scenario.value); open.value = false }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '提交失败，请重试' }
  finally { busy.value = false }
}
</script>
<style scoped>
.revision-layout { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
.revision-layout section { min-width:0; }
h3 { margin:0 0 12px; font-size:15px; }
.current-picture { height:370px; }
.file-input { display:none; }
.annotation-control { width:100%; }
.annotation-drop { width:100%; min-height:88px; padding:16px; border:1px dashed var(--el-border-color); border-radius:6px; background:var(--el-fill-color-blank); color:var(--el-text-color-regular); cursor:pointer; }
.annotation-drop:hover { border-color:var(--el-color-primary); }
.annotation-preview { width:130px; }
.annotation-preview .hx-picture { height:100px; }
.hx-footnote { line-height:1.6; }
@media(max-width:700px) { .revision-layout { grid-template-columns:1fr; } .current-picture { height:240px; } }
</style>
