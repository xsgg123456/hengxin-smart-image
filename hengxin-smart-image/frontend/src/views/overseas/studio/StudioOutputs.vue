<template>
  <div class="studio-image-attachments" aria-label="本轮输出文件">
    <div v-for="file in files" :key="file.id" class="studio-image-file">
      <span class="studio-doc-icon">文件</span>
      <div class="studio-image-file-meta"><span>{{ file.name }}</span><small>{{ formatAttachmentSize(file.sizeBytes) }}</small></div>
      <AttachmentDownload :url="file.url" :name="file.name" @failure="$emit('failure', $event)" />
    </div>
  </div>
</template>
<script setup lang="ts">
import type { StudioOutput } from '@/api/overseas/studio-outputs'
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import AttachmentDownload from '../AttachmentDownload.vue'
defineProps<{ files: StudioOutput[] }>()
defineEmits<{ failure: [reason: unknown] }>()
</script>
