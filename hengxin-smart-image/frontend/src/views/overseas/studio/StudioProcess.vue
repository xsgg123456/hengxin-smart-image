<template>
  <details v-if="content.entries.length" class="studio-execution studio-process" :open="open" @toggle="syncOpen">
    <summary><span>执行过程 · {{ content.entries.length }} 条记录</span><span>{{ open ? '收起' : '展开查看' }}</span></summary>
    <StudioTranscript :entries="content.entries" :running="turn.status !== 'succeeded'" />
  </details>
  <StudioMarkdown v-if="content.reply" :text="content.reply" />
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { StudioTranscript as Transcript, StudioTurn } from '@/api/overseas/studio'
import StudioTranscript from './StudioTranscript.vue'
import StudioMarkdown from './StudioMarkdown.vue'
import { splitStudioReply } from './studio-process'
const props = defineProps<{ turn: StudioTurn; entries: Transcript[] }>()
const content = computed(() => splitStudioReply(props.turn, props.entries))
const open = ref(props.turn.status !== 'succeeded')
watch(() => props.turn.status, status => { open.value = status !== 'succeeded' })
function syncOpen(event: Event) { open.value = (event.target as HTMLDetailsElement).open }
</script>
<style scoped>
.studio-process > summary { display: flex; justify-content: space-between; gap: 12px; }
.studio-process > summary span:last-child { flex-shrink: 0; }
</style>
