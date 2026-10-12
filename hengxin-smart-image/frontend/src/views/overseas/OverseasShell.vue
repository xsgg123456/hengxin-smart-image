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
import { onMounted } from 'vue'
import { useSettingStore } from '@/store/modules/setting'
import zh from 'element-plus/es/locale/lang/zh-cn'
import ArtSidebarMenu from '@/components/core/layouts/art-menus/art-sidebar-menu/index.vue'
import ArtHeaderBar from '@/components/core/layouts/art-header-bar/index.vue'
import ArtGlobalSearch from '@/components/core/layouts/art-global-search/index.vue'
const settings = useSettingStore()
onMounted(() => { if (window.innerWidth < 800) settings.setMenuOpen(false) })
</script>
<style lang="scss" scoped>
@use '../index/style';
</style>
