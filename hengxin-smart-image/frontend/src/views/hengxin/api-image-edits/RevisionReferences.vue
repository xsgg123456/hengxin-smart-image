<template>
  <div class="reference-inputs">
    <div class="input-header"><strong>{{ confirmation ? '本轮将发送' : '本轮输入图片' }} <span>{{ references.length + (hasAnnotation || annotationUrl ? 1 : 0) }} 张图片</span></strong><small>{{ confirmation ? '顺序与提示词一致' : '系统自动带入 · 点击图片放大对照' }}</small></div>
    <div :class="confirmation ? 'confirm-images' : 'input-strip'">
      <button v-for="(input, index) in references" :key="input.picture.fileId" :class="confirmation ? 'confirm-card' : 'input-card'" @click="show(input)">
        <img :src="input.picture.url" :alt="input.name"><div><b>图{{ index + 1 }} · {{ input.name }}</b><span>{{ input.role }}</span><small>点击放大</small></div>
      </button>
      <button v-if="annotationUrl" class="confirm-card" @click="show({ name: '标注图', role: '仅用于定位，不进入成品', picture: { fileId: '', name: '标注图', url: annotationUrl } })"><img :src="annotationUrl" alt="标注图"><b>图{{ references.length + 1 }} · 标注图</b><span>仅用于定位，不进入成品</span></button>
      <div v-else-if="!confirmation" class="input-card annotation-card"><div><b>{{ hasAnnotation ? `图${references.length + 1} · 标注图` : '标注图（可选）' }}</b><span>{{ hasAnnotation ? (marks ? `画布已标注 ${marks} 处` : '已上传标注图') : '未标注，不发送此图' }}</span></div></div>
    </div>
  </div>
  <ElDialog v-model="zoomOpen" :title="`${zoom?.name || ''} · 放大对照`" width="min(860px,92vw)" align-center append-to-body>
    <p class="hx-footnote">{{ zoom?.role }}</p><p v-if="loading" role="status">正在读取原始图片…</p><ElAlert v-if="loadError" :title="loadError" type="error" :closable="false"><ElButton text @click="loadZoom">重新加载</ElButton></ElAlert><img v-if="zoomUrl" class="zoom-image" :src="zoomUrl" :alt="zoom?.name" @error="loadError = '图片无法显示，请重新加载'"><template #footer><ElButton @click="zoomOpen = false">返回编辑</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { apiImages, errorText } from '@/api/api-image-edits'
import type { RevisionReference } from './revision-references'
defineProps<{ references: RevisionReference[]; hasAnnotation?: boolean; marks?: number; annotationUrl?: string; confirmation?: boolean }>()
const zoomOpen = ref(false), zoom = ref<RevisionReference>()
const zoomUrl = ref(''), loading = ref(false), loadError = ref('')
let generation = 0
function clearZoom() { generation++; if (zoomUrl.value.startsWith('blob:') && zoom.value?.picture.fileId) URL.revokeObjectURL(zoomUrl.value); zoomUrl.value = '' }
async function loadZoom() {
  clearZoom(); const token = generation; loadError.value = ''; loading.value = true
  try {
    const picture = zoom.value?.picture
    if (!picture) return
    const url = picture.fileId ? URL.createObjectURL(await apiImages.download(picture.fileId)) : picture.url
    if (token !== generation) { if (picture.fileId) URL.revokeObjectURL(url); return }
    zoomUrl.value = url
  } catch (error) { if (token === generation) loadError.value = errorText(error) }
  finally { if (token === generation) loading.value = false }
}
function show(input: RevisionReference) { clearZoom(); zoom.value = input; zoomOpen.value = true; void loadZoom() }
watch(zoomOpen, value => { if (!value) clearZoom() })
onBeforeUnmount(clearZoom)
</script>
<style scoped>
.reference-inputs { flex:none; min-width:0; margin-bottom:10px; }
.input-header { display:flex; justify-content:space-between; gap:8px; font-size:13px; margin-bottom:8px; }
.input-header span { color:var(--el-color-primary); font-weight:400; }
.input-header small, .input-card small { color:var(--el-text-color-secondary); }
.input-strip { display:flex; gap:8px; overflow-x:auto; padding-bottom:4px; }
.input-card, .confirm-card { border:1px solid var(--el-border-color); border-radius:8px; background:var(--el-bg-color); color:inherit; text-align:left; font:inherit; padding:8px; cursor:pointer; }
.input-card { display:flex; align-items:center; gap:8px; flex:1; min-width:145px; }
.input-card:hover, .confirm-card:hover { border-color:var(--el-color-primary); }
.input-card img { width:44px; height:58px; object-fit:contain; flex:none; }
.input-card b, .confirm-card b { font-size:12px; }
.input-card span, .input-card small, .confirm-card span { display:block; font-size:11px; line-height:1.7; }
.annotation-card { border-style:dashed; cursor:default; }
.confirm-images { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.confirm-card { min-width:0; }
.confirm-card img { width:100%; height:160px; object-fit:contain; display:block; margin-bottom:8px; }
.zoom-image { display:block; width:100%; max-height:65dvh; object-fit:contain; }
@media(max-width:1100px) { .input-header small, .input-card small { display:none; } .input-card { min-width:150px; } .input-card img { height:42px; } }
@media(max-width:900px) { .input-card { min-width:140px; padding:6px; } .input-card img { width:32px; height:32px; } .input-card span { display:none; } }
</style>
