<template>
  <ElCard class="art-card material-reader" shadow="never">
    <div class="reader-heading"><h2>图需资料</h2><span class="hx-muted">{{ files.length }} 份资料</span></div>
    <ElEmpty v-if="!files.length" description="暂无图需资料" />
    <template v-else>
      <ElTabs v-model="selected"><ElTabPane v-for="file in files" :key="file.id" :name="file.id" :label="file.name" /></ElTabs>
      <template v-if="current">
        <div class="reader-toolbar"><div class="file-label"><b>{{ current.name }}</b><span>{{ size }} · {{ current.status === 'ready' ? '解析成功' : '解析失败' }}</span></div>
          <div class="reader-actions"><ElButton @click="expanded = true">放大查看</ElButton><ElButton :loading="opening" @click="original(false)">新窗口打开</ElButton><ElButton type="primary" :loading="downloading" @click="original(true)">下载原文件</ElButton></div>
        </div>
        <div class="version-bar"><ElSelect v-model="version" aria-label="解析版本"><ElOption v-for="item in current.versions" :key="item.version" :value="item.version" :label="`第 ${item.version} 版 · ${item.status === 'ready' ? '成功' : '失败'}`" /></ElSelect>
          <ElRadioGroup v-if="isPdf" v-model="view"><ElRadioButton value="original">PDF 原件</ElRadioButton><ElRadioButton value="text">解析文本</ElRadioButton></ElRadioGroup><span class="hx-muted">{{ formatBeijingTime(parsed?.createdAt) }}</span></div>
        <ElAlert v-if="error || parsed?.error" :title="error || parsed?.error || ''" type="warning" :closable="false" />
        <template v-if="!expanded"><MaterialPdfReader v-if="isPdf && view === 'original'" :key="current.id" :file="current" :api="api" @failure="failure" /><MaterialTextReader v-else :key="`${current.id}-${version}`" :text="parsed?.text || ''" :name="current.name" /></template>
        <p class="reader-hint">在线阅读或下载原件后用本地软件审核。解析版本仅对应文本，下载始终为上传的原文件。</p>
      </template>
    </template>
    <ElDialog v-model="expanded" :title="current?.name || '图需资料'" width="min(1380px, 96vw)" append-to-body destroy-on-close class="material-expanded">
      <ElTabs v-if="expanded" v-model="selected"><ElTabPane v-for="file in files" :key="file.id" :name="file.id" :label="file.name" /></ElTabs>
      <div v-if="expanded && current" class="version-bar"><ElSelect v-model="version" aria-label="阅读窗口解析版本"><ElOption v-for="item in current.versions" :key="item.version" :value="item.version" :label="`第 ${item.version} 版 · ${item.status === 'ready' ? '成功' : '失败'}`" /></ElSelect><ElRadioGroup v-if="isPdf" v-model="view"><ElRadioButton value="original">PDF 原件</ElRadioButton><ElRadioButton value="text">解析文本</ElRadioButton></ElRadioGroup><span class="hx-muted">下载为上传的原文件</span></div>
      <template v-if="current && expanded"><div class="reader-actions expanded-actions"><ElButton :loading="opening" @click="original(false)">新窗口打开</ElButton><ElButton type="primary" :loading="downloading" @click="original(true)">下载原文件</ElButton></div><ElAlert v-if="error" :title="error" type="warning" :closable="false" /><MaterialPdfReader v-if="isPdf && view === 'original'" :file="current" :api="api" @failure="failure" /><MaterialTextReader v-else :text="parsed?.text || ''" :name="current.name" /></template>
      <template #footer><ElButton @click="expanded = false">收起预览</ElButton></template>
    </ElDialog>
  </ElCard>
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { materialError, type Material, type MaterialsApi } from '@/api/overseas/materials'
import MaterialPdfReader from './MaterialPdfReader.vue'
import MaterialTextReader from './MaterialTextReader.vue'
const props = defineProps<{ files: Material[]; api: MaterialsApi }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const selected = ref(''), version = ref(1), view = ref('original'), expanded = ref(false), error = ref(''), opening = ref(false), downloading = ref(false)
const current = computed(() => props.files.find(file => file.id === selected.value)), parsed = computed(() => current.value?.versions.find(v => v.version === version.value))
const isPdf = computed(() => current.value?.contentType === 'application/pdf'), size = computed(() => `${((current.value?.sizeBytes || 0) / 1024).toFixed(1)} KB`)
let epoch = 0, controller: AbortController | undefined, originalWindow: Window | null = null
const urls = new Set<string>()
function clear() { ++epoch; controller?.abort(); originalWindow?.close(); originalWindow = null; for (const url of urls) URL.revokeObjectURL(url); urls.clear(); opening.value = false; downloading.value = false; error.value = '' }
function failure(reason: unknown) { error.value = materialError(reason); if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) { clear(); expanded.value = false; emit('failure', reason) } }
watch(() => props.files.map(f => `${f.id}:${f.version}`).join(','), () => { if (!props.files.some(f => f.id === selected.value)) selected.value = props.files[0]?.id || ''; clear(); version.value = current.value?.version || 1; expanded.value = false }, { immediate: true })
watch(selected, () => { clear(); version.value = current.value?.version || 1; view.value = 'original' })
watch(version, () => { if (version.value !== current.value?.version) view.value = 'text' })
watch(expanded, value => { if (!value) clear() })
async function original(download: boolean) {
  const file = current.value, textSnapshot = parsed.value?.text
  if (!file || opening.value || downloading.value) return
  clear(); const id = epoch; controller = new AbortController(); error.value = ''
  if (!download) { originalWindow = window.open('about:blank', '_blank'); if (!originalWindow) { error.value = '浏览器拦截了新窗口，请允许弹窗或下载原文件'; return }; originalWindow.opener = null; originalWindow.document.title = file.name }
  opening.value = !download; downloading.value = download
  try {
    // Recheck permission even when showing previously parsed text in a new window.
    const blob = await props.api.content(file.id, download, controller.signal)
    if (id !== epoch) return
    if (download || file.contentType === 'application/pdf') {
      const url = URL.createObjectURL(blob); urls.add(url)
      if (download) { const a = document.createElement('a'); a.href = url; a.download = file.name; a.click(); setTimeout(() => { URL.revokeObjectURL(url); urls.delete(url) }, 60000) }
      else originalWindow?.location.replace(url)
    } else if (originalWindow) {
      const doc = originalWindow.document, heading = doc.createElement('h1'), hint = doc.createElement('p'), text = doc.createElement('pre')
      heading.textContent = file.name; hint.textContent = '安全文本预览，非原始版式；完整格式请在原页面下载后用本地软件打开。'
      text.textContent = textSnapshot || '没有可读取内容'; text.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font:15px sans-serif;padding:24px;background:#f7f9fc'
      doc.body.style.cssText = 'margin:32px;color:#39465c;font:14px sans-serif'; doc.body.replaceChildren(heading, hint, text)
    }
  } catch (reason) { if (id === epoch) { originalWindow?.close(); originalWindow = null; failure(reason) } }
  finally { if (id === epoch) { opening.value = false; downloading.value = false } }
}
onUnmounted(clear)
</script>
<style scoped>
.reader-heading,.reader-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }.reader-heading h2 { font-size: 16px; font-weight: 600; }
.reader-toolbar { border: 1px solid #e8ecf3; padding: 14px; border-radius: 8px 8px 0 0; }.file-label { min-width: 0; overflow-wrap: anywhere; }.file-label b { font-size: 14px; font-weight: 500; }.file-label span { display: block; color: #8b98aa; font-size: 12px; margin-top: 6px; }
.reader-actions { display: flex; gap: 8px; flex-wrap: wrap; }.reader-actions .el-button { margin: 0; }.expanded-actions { margin-bottom: 14px; justify-content: flex-end; }
.version-bar { display: flex; align-items: center; gap: 12px; padding: 12px 0; flex-wrap: wrap; }.version-bar .el-select { width: 170px; }.hx-muted,.reader-hint { color: #8b98aa; font-size: 12px; }.reader-hint { margin-top: 14px; }
:deep(.el-tabs__item) { max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
:global(.material-expanded) { margin: 4vh auto; }
</style>
