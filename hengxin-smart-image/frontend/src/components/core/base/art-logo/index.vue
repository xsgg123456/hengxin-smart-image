<!-- 系统logo -->
<template>
  <div class="flex-cc art-brand-logo">
    <img :style="logoStyle" :src="colorLogo" alt="恒鑫智图" class="brand-color" />
    <img :style="logoStyle" src="@imgs/brand/mark-white.svg" alt="恒鑫智图" class="brand-white" />
  </div>
</template>

<script setup lang="ts">
  import mark from '@imgs/brand/mark.svg'
  import smallMark from '@imgs/brand/mark-small.svg'

  defineOptions({ name: 'ArtLogo' })

  interface Props {
    /** logo 大小 */
    size?: number | string
  }

  const props = withDefaults(defineProps<Props>(), {
    size: 36
  })

  const logoStyle = computed(() => ({ width: `${props.size}px`, height: `${props.size}px` }))
  const colorLogo = computed(() => Number(props.size) <= 24 ? smallMark : mark)
</script>

<style scoped>
  .art-brand-logo { flex-shrink: 0; }
  img { display: block; object-fit: contain; }
  .brand-white { display: none; }
  :global(.dark .art-brand-logo .brand-color),
  :global(.menu-left-dark .art-brand-logo .brand-color) { display: none; }
  :global(.dark .art-brand-logo .brand-white),
  :global(.menu-left-dark .art-brand-logo .brand-white) { display: block; }
</style>
