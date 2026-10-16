<template>
  <div class="studio-image-attachments" :class="{ compact }">
    <div v-for="asset in visible" :key="asset.id" class="studio-image-file" :class="{ 'is-image': isImage(asset) }" :title="asset.name">
      <StudioAssetImage v-if="isImage(asset)" :asset="asset" :group="assets" :title="title" @failure="$emit('failure', $event)" />
      <span v-else class="studio-doc-icon">文档</span>
      <div class="studio-image-file-meta"><span :title="asset.name">{{ asset.name }}</span></div>
      <AttachmentDownload v-if="!isImage(asset)" :url="asset.url" :name="asset.name" @failure="$emit('failure', $event)" />
      <ElButton v-if="removable" class="remove-file" text :disabled="disabled" :aria-label="`移除 ${asset.name}`" @click="$emit('remove', asset.id)">×</ElButton>
    </div>
    <ElButton v-if="compact && assets.length > 3" class="all-files" text type="primary" @click="allOpen = true">查看全部<br>{{ assets.length }} 个附件</ElButton>
  </div>
  <ElDialog v-if="compact" v-model="allOpen" :title="`待发送附件 · ${assets.length}`" width="min(680px,94vw)" append-to-body class="studio-files-dialog">
    <StudioAttachments :assets="assets" :title="title" :removable="removable" :disabled="disabled" @remove="$emit('remove', $event)" @failure="$emit('failure', $event)" />
    <p v-if="!assets.length">暂无待发送附件</p><template #footer><ElButton @click="allOpen = false">完成</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { isImage, type StudioImage } from './studio-images'
import StudioAssetImage from './StudioAssetImage.vue'
import AttachmentDownload from '../AttachmentDownload.vue'
const props = defineProps<{ assets: StudioImage[]; title: string; removable?: boolean; compact?: boolean; disabled?: boolean }>()
defineEmits<{ remove: [id: string]; failure: [reason: unknown] }>()
const allOpen = ref(false), visible = computed(() => props.compact ? props.assets.slice(0, 3) : props.assets)
</script>
