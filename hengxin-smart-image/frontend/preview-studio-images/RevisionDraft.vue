<template>
  <div class="revision-draft">
    <div class="revision-thumbs"><AssetImage :asset="revision.base" :group="images" title="本次修改" /><AssetImage v-if="revision.annotation" :asset="revision.annotation" :group="images" title="本次修改" /></div>
    <div class="revision-summary"><strong :title="revision.base.name">修改 {{ revision.base.name }}</strong><small>{{ revision.annotation ? '已添加标注' : '待补充修改要求' }} · 待发送</small></div>
    <div class="revision-actions"><ElButton text size="small" type="primary" @click="detailsOpen = true">查看描述</ElButton><ElButton text size="small" type="primary" @click="$emit('edit')">继续标注</ElButton><ElButton text size="small" :aria-label="`取消修改 ${revision.base.name}`" title="取消本次修改" @click="$emit('remove')">×</ElButton></div>
  </div>
  <ElDialog v-model="detailsOpen" :title="`修改 ${revision.base.name}`" width="min(560px, 94vw)" append-to-body class="preview-files-dialog"><p class="revision-description">{{ revision.text || '尚未添加标注描述，请在工作台输入区补充修改要求。' }}</p><template #footer><ElButton @click="detailsOpen = false">关闭</ElButton><ElButton type="primary" @click="detailsOpen = false; $emit('edit')">继续标注</ElButton></template></ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Revision } from './state'
import AssetImage from './AssetImage.vue'
const props = defineProps<{ revision: Revision }>()
defineEmits<{ edit: []; remove: [] }>()
const images = computed(() => [props.revision.base, ...(props.revision.annotation ? [props.revision.annotation] : [])])
const detailsOpen = ref(false)
</script>
