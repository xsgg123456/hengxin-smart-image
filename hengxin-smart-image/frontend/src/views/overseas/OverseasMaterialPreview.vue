<template>
  <ElDialog v-model="open" title="图需资料预览" width="min(1180px, 94vw)" append-to-body destroy-on-close>
    <OverseasMaterialReader v-if="open && api && actualFiles.length" :files="actualFiles" :api="api" @failure="emit('failure', $event)" />
    <ElTabs v-else v-model="tab">
      <ElTabPane v-for="kind in kinds" :key="kind.key" :label="kind.label" :name="kind.key">
        <template v-if="material(kind.key)">
          <p class="hx-muted">{{ material(kind.key)?.name }}</p>
          <template v-if="realMaterial(kind.key)">
            <ElSelect v-model="selectedVersion" aria-label="解析版本" class="hx-gap">
              <ElOption v-for="version in realMaterial(kind.key)?.versions" :key="version.version" :value="version.version" :label="`第 ${version.version} 版 · ${version.status === 'ready' ? '成功' : '失败'}`" />
            </ElSelect>
            <p class="hx-muted hx-gap">{{ parsed(kind.key)?.createdAt }}</p>
            <ElAlert v-if="parsed(kind.key)?.error" :title="parsed(kind.key)?.error || ''" type="error" :closable="false" />
            <pre class="material-text hx-gap">{{ parsed(kind.key)?.text || '本版本未解析出可读内容' }}</pre>
            <p class="hx-muted hx-gap">{{ realMaterial(kind.key)?.contentType === 'application/pdf' ? 'PDF 可预览原件或下载。' : '此格式请下载后使用本地应用打开。' }}</p>
            <div class="hx-filter hx-gap"><ElButton v-if="realMaterial(kind.key)?.contentType === 'application/pdf'" :disabled="loading" @click="original(realMaterial(kind.key)!, false)">预览原件</ElButton><ElButton :disabled="loading" @click="original(realMaterial(kind.key)!, true)">下载原件</ElButton></div>
          </template>
          <ElAlert v-else class="hx-gap" :closable="false" type="info" :title="sample(kind.key) ? '以下为内置示例资料，供体验文件预览流程。' : '已选择本地文件；本轮仅展示文件信息，尚未接入真实内容解析。'" />
          <template v-if="sample(kind.key)">
            <h3 class="hx-gap">{{ kind.label }} · 示例内容</h3>
            <ElTable :data="kind.key === 'requirement' ? requirement : competitor" class="hx-gap">
              <ElTableColumn prop="item" label="项目" min-width="120" />
              <ElTableColumn prop="description" label="内容" min-width="220" />
            </ElTable>
          </template>
        </template>
        <ElEmpty v-else description="未提供该资料；提交任意一份即可" />
      </ElTabPane>
    </ElTabs>
    <p v-if="loading" role="status">正在读取原件…</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <p v-if="originalUrl" class="hx-muted hx-gap">原件已在独立窗口打开，关闭资料预览时同步关闭。</p>
    <template #footer><ElButton @click="open = false">关闭</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import OverseasMaterialReader from './OverseasMaterialReader.vue'
import type { Material as PreviewMaterial } from './types'
import { materialError, type Material, type MaterialsApi } from '@/api/overseas/materials'
const props = defineProps<{ files: (PreviewMaterial | Material)[]; api?: MaterialsApi }>()
const actualFiles = computed(() => props.files.filter((file): file is Material => 'id' in file))
const emit = defineEmits<{ failure: [reason: unknown] }>()
const open = defineModel<boolean>({ required: true })
const tab = ref(props.files[0]?.kind || 'requirement'), selectedVersion = ref(1), loading = ref(false), error = ref(''), originalUrl = ref('')
const kinds = [{ key: 'requirement', label: '图片需求文件' }, { key: 'competitor', label: '竞品分析表格' }] as const
const material = (kind: Material['kind']) => props.files.find(file => file.kind === kind)
const realMaterial = (kind: Material['kind']) => { const value = material(kind); return value && 'id' in value ? value : undefined }
const sample = (kind: Material['kind']) => { const value = material(kind); return value && 'sample' in value && value.sample }
const parsed = (kind: Material['kind']) => realMaterial(kind)?.versions.find(v => v.version === selectedVersion.value)
let generation = 0, controller: AbortController | undefined, originalWindow: Window | null = null
function clearOriginal() { ++generation; controller?.abort(); originalWindow?.close(); originalWindow = null; if (originalUrl.value) URL.revokeObjectURL(originalUrl.value); originalUrl.value = ''; loading.value = false; error.value = '' }
watch([open, tab, () => props.files], () => { clearOriginal(); if (!material(tab.value)) tab.value = props.files[0]?.kind || 'requirement'; selectedVersion.value = realMaterial(tab.value)?.version || 1 })
async function original(file: Material, download: boolean) {
  if (!props.api || loading.value) return
  clearOriginal()
  if (!download) {
    originalWindow = window.open('about:blank', '_blank')
    if (!originalWindow) { error.value = '原件窗口被浏览器拦截，请允许弹窗后重试或下载原件'; return }
    originalWindow.opener = null
    originalWindow.document.title = '正在读取 PDF 原件'
  }
  const current = generation; controller = new AbortController(); loading.value = true
  try {
    const blob = await props.api.content(file.id, download, controller.signal)
    if (current !== generation || !open.value) return
    const url = URL.createObjectURL(blob)
    if (download) { const link = document.createElement('a'); link.href = url; link.download = file.name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) }
    else { originalUrl.value = url; originalWindow?.location.replace(url) }
  } catch (reason) { if (current === generation) { originalWindow?.close(); originalWindow = null; error.value = materialError(reason); emit('failure', reason) } }
  finally { if (current === generation) loading.value = false }
}
onUnmounted(clearOriginal)
const requirement = [
  { item: '图片目标', description: '主图呈现产品全貌，卖点图说明细节，场景图表现使用方式。' },
  { item: '视觉要求', description: '突出清透与轻薄，整套图片保持一致的品牌视觉。' },
  { item: 'SKU 对应', description: '各 SKU 独立安排图片；具体数量及文案由方案确认。' }
]
const competitor = [
  { item: '示例竞品 A', description: '产品主体突出；卖点图层级清晰。' },
  { item: '示例竞品 B', description: '使用场景明确；细节特写便于理解功能。' }
]
</script>

<style scoped>
.material-text { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 400px; overflow-y: auto; }
.hx-filter { flex-wrap: wrap; }
</style>
