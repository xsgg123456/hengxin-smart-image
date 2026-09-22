<template>
  <ElAlert v-if="storageError" :title="storageError" type="error" :closable="false" show-icon />
  <details v-if="isMockMode && !route.path.startsWith('/management/') && !route.path.startsWith('/api-image-edits/')" class="hx-demo-tools">
    <summary>模拟预览 · 示例图片 <span>展开调试工具</span></summary>
  <div v-if="isMockMode && !route.path.startsWith('/management/') && !route.path.startsWith('/api-image-edits/')" class="hx-filter hx-gap">
    <ElSelect :model-value="role" aria-label="预览角色" style="width: 170px" @change="changeRole"><ElOption v-for="item in previewRoles" :key="item.value" :value="item.value" :label="item.label" /></ElSelect>
    <ElSelect :model-value="scenario" aria-label="模拟场景" style="width: 180px" @change="changeScenario">
      <ElOption v-for="item in scenarios" :key="item.value" :value="item.value" :label="item.label" />
    </ElSelect><span class="hx-muted">{{ isDemoMode ? '角色共用数据；每个场景独立保存。失败场景首次失败，重试恢复。' : '切换场景会刷新并重置模拟数据。' }}</span><DemoReset v-if="isDemoMode" />
  </div>
  </details>
  <div v-if="connection.error" class="hx-gap" role="alert">
    <ElAlert :title="connection.error" type="error" :closable="false" show-icon />
    <ElButton class="hx-gap" :loading="connection.loading" @click="retry">重新加载</ElButton>
  </div>
</template>
<script setup lang="ts">
import { isMockMode, isDemoMode } from '../../../api/hengxin/client'
import DemoReset from './DemoReset.vue'
import { ref, onBeforeUnmount } from 'vue'
const storageError = ref('')
const onStorageError = (event: Event) => { storageError.value = (event as CustomEvent<string>).detail }
window.addEventListener('hengxin:demo-storage-error', onStorageError)
onBeforeUnmount(() => window.removeEventListener('hengxin:demo-storage-error', onStorageError))
import { previewRoles } from '../../../api/hengxin/session'
import { useRoute } from 'vue-router'
const route = useRoute()
import { connection, refreshWorkspace } from '../model'
const scenarios = [
  { value: 'default', label: '常规预览' }, { value: 'empty', label: '空工作区' },
  { value: 'no-skills', label: '无可用 Skill' }, { value: 'upload-error', label: '上传失败与重试' },
  { value: 'save-error', label: '保存失败与重试' }, { value: 'submit-error', label: '提交失败与重试' },
  { value: 'list-error', label: '列表失败与重试' },
  { value: 'execution-error', label: '生成执行失败' }, { value: 'partial-result', label: '部分图片失败' },
  { value: 'revision-error', label: '返工失败保留旧图' }, { value: 'archive-error', label: '归档失败与重试' }
]
const scenario = new URLSearchParams(window.location.search).get('scenario') || 'default'
const role = new URLSearchParams(window.location.search).get('role') || 'operator'
function changeRole(value: string) { const url = new URL(window.location.href); url.searchParams.set('role', value); window.location.assign(url.href) }
function changeScenario(value: string) {
  const url = new URL(window.location.href)
  url.searchParams.set('scenario', value)
  window.location.assign(url.href)
}
async function retry() { try { await refreshWorkspace() } catch { /* 保留错误提示 */ } }
</script>

<style scoped>
.hx-demo-tools { margin-bottom:8px; border:1px solid var(--default-border); border-radius:6px; font-size:12px; color:var(--art-gray-600); }
.hx-demo-tools summary { cursor:pointer; padding:7px 12px; }
.hx-demo-tools summary span { margin-left:12px; color:var(--el-color-primary); }
.hx-demo-tools .hx-filter { padding:0 12px; margin:8px 0 12px; gap:12px; }
</style>
