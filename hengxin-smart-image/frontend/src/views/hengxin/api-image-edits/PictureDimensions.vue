<template>
  <span class="picture-dimensions">{{ size ? `${size.width} × ${size.height} px` : '尺寸未知' }}</span>
  <ElTag v-if="mismatch" size="small" type="warning">尺寸不一致</ElTag>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Picture } from '@/types/hengxin'
import type { ApiPicture } from '@/types/api-image-edits'
type DimensionPicture = Picture & Pick<ApiPicture, 'width' | 'height'>
const props = defineProps<{ picture?: DimensionPicture | null; source?: DimensionPicture | null }>()
function dimensions(picture?: DimensionPicture | null) {
  const width = picture?.width, height = picture?.height
  return typeof width === 'number' && Number.isSafeInteger(width) && width > 0
    && typeof height === 'number' && Number.isSafeInteger(height) && height > 0 ? { width, height } : null
}
const size = computed(() => dimensions(props.picture))
const mismatch = computed(() => {
  const original = dimensions(props.source)
  return !!(size.value && original && (size.value.width !== original.width || size.value.height !== original.height))
})
</script>
<style scoped>
.picture-dimensions { font-size:12px; font-weight:normal; color:var(--art-gray-600); }
</style>
