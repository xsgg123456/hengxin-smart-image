<template>
  <div class="preview-attachments" :class="{ compact }">
    <div v-for="asset in visible" :key="asset.id" class="preview-file" :class="{ 'is-image': asset.image }">
      <AssetImage v-if="asset.image" :asset="asset" :group="assets" :title="title" />
      <a v-else :href="asset.url" :download="asset.name" class="preview-doc-icon" title="下载原文件">文档</a>
      <div class="preview-file-meta"><span :title="asset.name">{{ asset.name }}</span></div>
      <ElButton v-if="removable" class="remove-file" text :aria-label="`移除 ${asset.name}`" @click="$emit('remove', asset.id)">×</ElButton>
    </div>
    <ElButton v-if="compact && assets.length > 3" class="all-files" text type="primary" @click="allOpen = true">查看全部<br>{{ assets.length }} 个附件</ElButton>
  </div>
  <ElDialog v-if="compact" v-model="allOpen" :title="`待发送附件 · ${assets.length}`" width="min(680px, 94vw)" append-to-body class="preview-files-dialog">
    <Attachments :assets="assets" :title="title" :removable="removable" @remove="$emit('remove', $event)" />
    <p v-if="!assets.length">暂无待发送附件</p>
    <template #footer><ElButton @click="allOpen = false">完成</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Asset } from './state'
import AssetImage from './AssetImage.vue'
const props = defineProps<{ assets: Asset[]; title: string; removable?: boolean; compact?: boolean }>()
defineEmits<{ remove: [id: string] }>()
const allOpen = ref(false)
const visible = computed(() => props.compact ? props.assets.slice(0, 3) : props.assets)
</script>
