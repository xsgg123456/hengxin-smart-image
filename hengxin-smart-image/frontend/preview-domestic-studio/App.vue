<template>
  <OverseasShell>
    <template #account><span class="hx-demo-badge">交互预览</span><ElAvatar :size="32" :title="previewActor.name">{{ previewActor.name.slice(0, 1) }}</ElAvatar><ElButton text type="primary" @click="explain">切换业务</ElButton><ElButton text type="primary" @click="explain">退出登录</ElButton></template>
    <ArtPageContent />
  </OverseasShell>
</template>
<script setup lang="ts">
import { previewActor } from './state'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import ArtPageContent from '@/components/core/layouts/art-page-content/index.vue'
function explain() { ElMessage.info('当前为独立交互预览，未连接真实业务。') }
</script>
