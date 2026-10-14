<template>
  <template v-for="entry in entries" :key="entry.itemId">
    <StudioMarkdown v-if="entry.kind === 'message'" :text="entry.text" />
    <details v-else class="studio-execution" :open="running">
      <summary>{{ labels[entry.kind] }} · {{ states[entry.state] }}</summary>
      <StudioMarkdown :text="entry.text" />
    </details>
  </template>
</template>
<script setup lang="ts">
import type { StudioTranscript } from '@/api/overseas/studio'
import StudioMarkdown from './StudioMarkdown.vue'
defineProps<{ entries: StudioTranscript[]; running: boolean }>()
const labels = { reasoning: '公开摘要', tool: '执行消息', notice: '状态通知' }
const states = { running: '进行中', completed: '已完成', failed: '未完成' }
</script>
