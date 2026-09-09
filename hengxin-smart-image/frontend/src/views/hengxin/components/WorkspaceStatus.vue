<template>
  <ElAlert v-if="isMockMode" title="前端模拟预览 · 生成返回示例图片，数据仅在本次页面打开期间保留，刷新后重置。" type="warning" :closable="false" show-icon />
  <div v-if="isMockMode" class="hx-filter hx-gap">
    <ElSelect :model-value="scenario" aria-label="模拟场景" style="width: 180px" @change="changeScenario">
      <ElOption v-for="item in scenarios" :key="item.value" :value="item.value" :label="item.label" />
    </ElSelect><span class="hx-muted">切换场景会刷新页面并重置模拟数据；失败场景首次失败，重试恢复。</span>
  </div>
  <div v-if="connection.error" class="hx-gap" role="alert">
    <ElAlert :title="connection.error" type="error" :closable="false" show-icon />
    <ElButton class="hx-gap" :loading="connection.loading" @click="retry">重新加载</ElButton>
  </div>
</template>
<script setup lang="ts">
import { isMockMode } from '../../../api/hengxin/client'
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
function changeScenario(value: string) {
  const url = new URL(window.location.href)
  url.searchParams.set('scenario', value)
  window.location.assign(url.href)
}
async function retry() { try { await refreshWorkspace() } catch { /* 保留错误提示 */ } }
</script>
