<template>
  <OverseasShell>
    <template #account><span class="hx-demo-badge">恒鑫智图工作区</span><ElAvatar :size="32">{{ admin ? '管' : previewRole === 'operator' ? '运' : '设' }}</ElAvatar><ElButton text type="primary" @click="explain">切换业务</ElButton><ElButton text type="primary" @click="explain">退出登录</ElButton></template>
    <ArtPageContent />
  </OverseasShell>
</template>
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { admin, previewRole } from './state'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import ArtPageContent from '@/components/core/layouts/art-page-content/index.vue'
function explain() { ElMessage.info('当前是独立交互预览，未连接登录或业务服务。') }
</script>
