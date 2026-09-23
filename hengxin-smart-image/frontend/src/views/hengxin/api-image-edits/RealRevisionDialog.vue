<template>
  <ElDialog v-model="open" title="修改这张结果" width="min(900px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy && !reading" :show-close="!busy && !reading">
    <div v-if="item?.result" class="revision-layout">
      <section><h3>当前生成结果 · 原图 {{ item.position }} · V{{ baseVersion }}</h3><div class="current-picture"><PicturePreview :picture="item.versions.find(v => v.number === baseVersion)?.picture || item.result" title="本次修改基于当前结果" /></div><p class="hx-footnote">以当前 V{{ baseVersion }} 为基础修改；成功后新增版本并设为当前，历史图片保留。</p></section>
      <section>
        <ElForm label-position="top">
          <ElFormItem label="修改说明"><ElInput v-model="text" aria-label="修改说明" type="textarea" :rows="6" maxlength="4000" show-word-limit placeholder="写下需要调整的地方，也可以只上传标注图。" :disabled="locked" /></ElFormItem>
          <ElFormItem label="标注图（可选，最多 1 张）">
            <div class="annotation-control">
              <input ref="picker" class="file-input" type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" aria-label="上传修改标注图" @change="readAnnotation" />
              <div v-if="annotation" class="annotation-preview"><PicturePreview :picture="annotation" title="修改标注图" /><ElButton text type="danger" :disabled="locked || reading" @click="removeAnnotation">移除标注图</ElButton></div>
              <ElButton v-else :loading="reading" :disabled="locked" @click="picker?.click()">选择 JPG / PNG 标注图</ElButton>
              <p class="hx-footnote">单张不超过 10 MiB。系统将自动附带对应原图和共用素材作为参考；标注图仅用于定位问题。</p>
            </div>
          </ElFormItem>
        </ElForm>
        <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <p v-else class="hx-footnote">修改说明与标注图至少填写一种。</p>
      </section>
    </div>
    <template #footer><ElButton :disabled="busy || reading" @click="open = false">关闭</ElButton><ElButton type="primary" :loading="busy" :disabled="reading || blocked || (!pending && !text.trim() && !annotation)" @click="submit">{{ pending ? '确认原修改请求' : '提交单图修改' }}</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { apiImages, errorText } from '@/api/api-image-edits'
import type { ApiPicture, ApiTask } from '@/types/api-image-edits'
import PicturePreview from '../components/PicturePreview.vue'
import { itemCommand } from './item-command'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: ApiTask; itemId: string; blocked?: boolean }>()
const emit = defineEmits<{ accepted: [] }>()
const user = String(useUserStore().getUserInfo.userId)
const item = computed(() => props.task.items.find(i => i.id === props.itemId)!)
const operation = computed(() => itemCommand(user, props.task.id, props.itemId))
const pending = computed(() => operation.value.state.pending)
const busy = computed(() => operation.value.state.busy)
const locked = computed(() => busy.value || !!pending.value)
const text = ref(''), annotation = ref<ApiPicture>(), baseVersion = ref(0), localError = ref('')
const error = computed(() => localError.value || operation.value.state.error)
const reading = ref(false), picker = ref<HTMLInputElement>()
let alive = true
watch([open, () => props.itemId], () => {
  if (!open.value) { if (!pending.value) void removeAnnotation(); return }
  const command = pending.value?.command
  if (command?.kind === 'revise') { text.value = command.input.text; annotation.value = command.annotation; baseVersion.value = command.input.baseVersion }
  else { text.value = ''; baseVersion.value = item.value?.currentVersion || 0 }
  localError.value = ''
}, { immediate: true })
async function removeAnnotation() {
  if (locked.value || !annotation.value) return
  const saved = annotation.value
  reading.value = true
  try { await apiImages.deleteFile(saved.fileId); if (annotation.value === saved) annotation.value = undefined }
  catch (e) { localError.value = '清理标注图失败：' + errorText(e) }
  finally { reading.value = false }
}
async function readAnnotation(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]; input.value = ''
  if (!file || locked.value || reading.value) return
  localError.value = ''
  if (!['image/jpeg', 'image/png'].includes(file.type) || !/\.(jpe?g|png)$/i.test(file.name)) { localError.value = '请选择 JPG 或 PNG 图片'; return }
  if (!file.size || file.size > 10 * 1024 * 1024) { localError.value = '标注图不能为空或超过 10 MiB'; return }
  reading.value = true
  let url = ''
  try {
    const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer())
    const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
    const png = [137, 80, 78, 71, 13, 10, 26, 10].every((byte, i) => bytes[i] === byte)
    if ((file.type === 'image/jpeg' && !jpeg) || (file.type === 'image/png' && !png)) throw new Error('图片内容与格式不符')
    url = URL.createObjectURL(file); const image = new Image(); image.src = url; await image.decode()
    if (!image.naturalWidth || !image.naturalHeight) throw new Error('图片无法解码')
    const saved = await apiImages.upload(file)
    if (!alive || !open.value) await apiImages.deleteFile(saved.fileId)
    else annotation.value = saved
  } catch (e) { localError.value = errorText(e) }
  finally { if (url) URL.revokeObjectURL(url); reading.value = false }
}
async function submit() {
  if (busy.value || reading.value || props.blocked || (!pending.value && !text.value.trim() && !annotation.value)) return
  if (!pending.value && item.value.currentVersion !== baseVersion.value) { localError.value = '当前版本已更新，请关闭后重新打开修改。'; return }
  const accepted = await operation.value.submit({ kind: 'revise', input: { baseVersion: baseVersion.value, text: text.value.trim(), annotationFileId: annotation.value?.fileId }, annotation: annotation.value }, (command, key) => {
    if (command.kind !== 'revise') throw new Error('请先确认此图片尚未完成的操作')
    return apiImages.revise(props.task.id, props.itemId, command.input, key)
  })
  if (accepted) { annotation.value = undefined; open.value = false; emit('accepted') }
}
onBeforeUnmount(() => { alive = false; if (!pending.value && !busy.value) void removeAnnotation() })
</script>
<style scoped>
.revision-layout { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
.revision-layout section { min-width:0; }
h3 { margin:0 0 12px; font-size:15px; }
.current-picture { height:370px; }
.file-input { display:none; }
.annotation-control { width:100%; }
.annotation-preview { width:130px; }
.annotation-preview .hx-picture { height:100px; }
.hx-footnote { line-height:1.6; }
@media(max-width:700px) { .revision-layout { grid-template-columns:1fr; } .current-picture { height:240px; } }
</style>
