<template>
  <ElConfigProvider :locale="zh" :z-index="3000">
    <div class="app-layout">
      <aside id="app-sidebar"><ArtSidebarMenu /></aside>
      <main id="app-main">
        <div id="app-header"><ArtHeaderBar><template #account><slot name="account" /></template></ArtHeaderBar></div>
        <div id="app-content"><slot /></div>
      </main>
      <ArtGlobalSearch />
    </div>
  </ElConfigProvider>
</template>
<script setup lang="ts">
import zh from 'element-plus/es/locale/lang/zh-cn'
import ArtSidebarMenu from '@/components/core/layouts/art-menus/art-sidebar-menu/index.vue'
import ArtHeaderBar from '@/components/core/layouts/art-header-bar/index.vue'
import ArtGlobalSearch from '@/components/core/layouts/art-global-search/index.vue'
</script>
<style lang="scss" scoped>
@use '../index/style';
</style>
