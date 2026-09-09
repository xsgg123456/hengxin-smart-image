<template>
  <ElAlert v-if="isMockMode" title="前端模拟预览 · 生成返回示例图片，数据仅在本次页面打开期间保留，刷新后重置。" type="warning" :closable="false" show-icon />
  <div v-if="connection.error" class="hx-gap" role="alert">
    <ElAlert :title="connection.error" type="error" :closable="false" show-icon />
    <ElButton class="hx-gap" :loading="connection.loading" @click="retry">重新加载</ElButton>
  </div>
</template>
<script setup lang="ts">
import { isMockMode } from '../../../api/hengxin/client'
import { connection, refreshWorkspace } from '../model'
async function retry() { try { await refreshWorkspace() } catch { /* 保留错误提示 */ } }
</script>
