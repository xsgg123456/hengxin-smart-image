<template>
  <div ref="scroller" class="studio-messages" aria-live="polite" @scroll="trackScroll" @load.capture="followBottom">
    <div v-if="!turns.length" class="studio-empty"><h2>从你的设计需求开始</h2><p>按需选择 Skill，引用任务素材，直接告诉 Codex 你想怎么做。</p></div>
    <template v-for="(turn, index) in turns" :key="turn.id">
      <div v-if="index === 0 || turn.conversationId !== turns[index - 1].conversationId" class="studio-conversation-divider">{{ turn.conversationId && turn.conversationId === conversationId ? '当前对话' : '历史对话' }}</div>
      <article class="studio-message user"><div class="studio-message-name">设计师</div><div class="studio-bubble"><ElTag v-if="turn.skillName">{{ turn.skillName }}</ElTag><p>{{ turn.text }}</p><StudioAttachments :assets="[...turn.attachments, ...turn.referencePictures]" title="本条消息" @failure="$emit('failure', $event)" /></div></article>
      <article class="studio-message assistant"><div class="studio-message-name">Codex <small>{{ labels[turn.status] || turn.status }}</small></div><div class="studio-bubble">
        <StudioProcess :turn="turn" :entries="byTurn.get(turn.id) || []" />
        <ElAlert v-if="turn.error" :title="turn.error" type="error" :closable="false" />
        <ElAlert v-if="turn.deliveryError" :title="turn.deliveryError" type="warning" :closable="false" />
        <div v-if="turn.pictures.length" class="studio-selection-bar"><ElCheckbox :model-value="turn.pictures.every(p => selected.includes(p.id))" :indeterminate="turn.pictures.some(p => selected.includes(p.id)) && !turn.pictures.every(p => selected.includes(p.id))" :disabled="disabled" @change="$emit('group', turn.pictures)">全选本组</ElCheckbox><span>已选 {{ turn.pictures.filter(p => selected.includes(p.id)).length }} / {{ turn.pictures.length }} 张</span></div>
        <div class="studio-pictures"><div v-for="picture in turn.pictures" :key="picture.id" class="studio-picture" :class="{ selected: selected.includes(picture.id) }">
          <StudioAssetImage :asset="picture" :group="turn.pictures" title="本组生成图片" @failure="$emit('failure', $event)" />
          <div class="studio-picture-footer"><ElCheckbox :model-value="selected.includes(picture.id)" :disabled="disabled" @change="$emit('toggle', picture.id)">{{ picture.name }}</ElCheckbox><ElButton text size="small" type="primary" :disabled="disabled" @click="$emit('modify', picture)">修改这张</ElButton><span v-if="picture.archived">已归档 · {{ picture.sku }}</span></div>
        </div></div>
      </div></article>
    </template>
    <div v-if="conversationId && turns.length && turns[turns.length - 1].conversationId !== conversationId" class="studio-conversation-divider">当前对话 · 可以开始新的设计需求</div>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUpdate, onUpdated, onMounted, onBeforeUnmount, ref } from 'vue'
import type { StudioTranscript as Transcript, StudioPicture, StudioTurn } from '@/api/overseas/studio'
import StudioAttachments from './StudioAttachments.vue'
import StudioAssetImage from './StudioAssetImage.vue'
import StudioProcess from './StudioProcess.vue'
const props = defineProps<{ turns: StudioTurn[]; transcript: Transcript[]; conversationId?: string | null; selected: string[]; disabled: boolean; scrollPosition?: number | null }>()
const emit = defineEmits<{ 'scroll-position': [position: number, conversationId?: string | null]; failure: [reason: unknown]; group: [pictures: StudioPicture[]]; toggle: [id: string]; modify: [picture: StudioPicture] }>()
const labels: Record<string, string> = { queued: '排队中', running: '执行中', collecting: '收取结果中', cancelling: '正在停止', uncertain: '执行状态待核实', succeeded: '已回复', failed: '执行失败', cancelled: '已停止' }
const byTurn = computed(() => {
  const result = new Map<string, Transcript[]>()
  for (const entry of props.transcript) { const items = result.get(entry.turnId) || []; items.push(entry); result.set(entry.turnId, items) }
  return result
})
const scroller = ref<HTMLElement>()
let nearBottom = true
function trackScroll() { const node = scroller.value; if (node) { nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 64; emit('scroll-position', node.scrollTop, props.conversationId) } }
function followBottom() { if (nearBottom && scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight }
onMounted(() => { if (scroller.value && props.scrollPosition != null) { scroller.value.scrollTop = props.scrollPosition; trackScroll() } else followBottom() })
onBeforeUnmount(trackScroll)
// Read the old DOM before patching: a pending browser scroll event must not lose a user's position.
onBeforeUpdate(trackScroll)
onUpdated(followBottom)
</script>
