<template>
  <section class="dc-page hx-page">
    <header class="dc-title"><h1>关于我们</h1></header>
    <ElCard shadow="never" class="art-card about-card"><ArtLogo class="about-logo" /><h2>公司介绍</h2><p>公司介绍正在准备中。</p></ElCard>
  </section>
</template>
<script setup lang="ts">
import ArtLogo from '@/components/core/base/art-logo/index.vue'
</script>
<style scoped>
.about-card { margin-top: 24px; }
.about-card :deep(.el-card__body) { text-align: center; padding: 64px 24px; }
.about-logo { width: 44px; height: 44px; margin: 0 auto 16px; }
.about-card h2 { font-size: 18px; font-weight: 600; }
.about-card p { color: var(--el-text-color-secondary); font-size: 14px; margin-top: 8px; }
</style>
