<template>
  <OverseasShell>
    <template #account><span class="hx-demo-badge">交互预览 · 示例数据</span><ElAvatar :size="32">张</ElAvatar><ElButton text type="primary" @click="explain">切换业务</ElButton><ElButton text type="primary" @click="explain">退出登录</ElButton></template>
    <ArtPageContent />
  </OverseasShell>
</template>
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import ArtPageContent from '@/components/core/layouts/art-page-content/index.vue'
function explain() { ElMessage.info('当前是独立换图记录预览，使用示例身份与数据。') }
</script>
