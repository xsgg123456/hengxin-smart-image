<template>
  <div ref="scroller" class="studio-messages" aria-live="polite" @scroll="trackScroll" @load.capture="followBottom">
    <div v-if="!turns.length && !hideEmptyGuide" class="studio-empty"><h2>从你的设计需求开始</h2><p>按需选择 Skill，引用任务素材，直接告诉 Codex 你想怎么做。</p></div>
    <template v-for="(turn, index) in turns" :key="turn.id">
      <div v-if="index === 0 || turn.conversationId !== turns[index - 1].conversationId" class="studio-conversation-divider">{{ turn.conversationId && turn.conversationId === conversationId ? '当前对话' : '历史对话' }}</div>
      <article class="studio-message user"><div class="studio-message-name">{{ turn.actor?.name?.trim() || '未知操作人' }}<small title="北京时间">{{ formatBeijingTime(turn.createdAt, '时间未记录') }}</small></div><div class="studio-bubble"><ElTag v-if="turn.skillName && !hideSkillLabels">{{ turn.skillName }}</ElTag><p>{{ turn.text }}</p><StudioAttachments :assets="[...turn.attachments, ...turn.referencePictures]" title="本条消息" @failure="$emit('failure', $event)" /><ElButton v-if="turn.imageEdits?.length" text type="primary" @click="history = turn">查看本轮修改材料（{{ turn.imageEdits.length }}张）</ElButton></div></article>
      <article class="studio-message assistant"><div class="studio-message-name">Codex <small>{{ labels[turn.status] || turn.status }}</small><small v-if="replyTime(turn)" title="北京时间">{{ replyTime(turn) }}</small></div><div class="studio-bubble">
        <StudioProcess :turn="turn" :entries="byTurn.get(turn.id) || []" />
        <ElAlert v-if="turn.error" :title="turn.error" type="error" :closable="false" />
        <ElAlert v-if="turn.deliveryError" :title="turn.deliveryError" type="warning" :closable="false" />
        <ElAlert v-if="deliveryProgress(turn)" :title="deliveryProgress(turn)" type="info" :closable="false" />
        <StudioOutputs v-if="turn.outputs?.length" :files="turn.outputs" @failure="$emit('failure', $event)" />
        <div v-if="turn.pictures.length && !simplePictures" class="studio-selection-bar"><ElCheckbox :model-value="turn.pictures.every(p => selected.includes(p.id))" :indeterminate="turn.pictures.some(p => selected.includes(p.id)) && !turn.pictures.every(p => selected.includes(p.id))" :disabled="disabled" @change="$emit('group', turn.pictures)">全选本组</ElCheckbox><span>已选 {{ turn.pictures.filter(p => selected.includes(p.id)).length }} / {{ turn.pictures.length }} 张</span><ElButton size="small" type="primary" plain :disabled="disabled" @click="$emit('batch-modify', turn.pictures)">批量标注</ElButton></div>
        <div v-else-if="turn.pictures.length && batchAnnotation" class="studio-selection-bar"><ElButton size="small" type="primary" plain :disabled="disabled" @click="$emit('batch-modify', turn.pictures)">批量标注</ElButton></div>
        <div class="studio-pictures"><div v-for="picture in turn.pictures" :key="picture.id" class="studio-picture" :class="{ selected: selected.includes(picture.id) }">
          <StudioAssetImage :asset="picture" :group="turn.pictures" title="本组生成图片" @failure="$emit('failure', $event)" />
          <div class="studio-picture-footer"><span v-if="simplePictures">{{ picture.name }}</span><ElCheckbox v-else :model-value="selected.includes(picture.id)" :disabled="disabled" @change="$emit('toggle', picture.id)">{{ picture.name }}</ElCheckbox><ElButton text size="small" type="primary" :disabled="disabled" @click="$emit('modify', picture)">修改这张</ElButton><span v-if="picture.archived">已归档 · {{ picture.sku }}</span></div>
        </div></div>
      </div></article>
    </template>
    <div v-if="conversationId && turns.length && turns[turns.length - 1].conversationId !== conversationId" class="studio-conversation-divider">当前对话 · 可以开始新的设计需求</div>
  </div>
  <ElDialog :model-value="!!history" title="本轮修改材料" width="min(980px,94vw)" append-to-body class="batch-review-dialog" @update:model-value="!$event && (history = undefined)"><StudioRevisionDetails v-if="history" :items="historicalRevisions(history)" @failure="$emit('failure', $event)" /><template #footer><ElButton @click="history = undefined">关闭</ElButton></template></ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUpdate, onUpdated, onMounted, onBeforeUnmount, ref } from 'vue'
import type { StudioTranscript as Transcript, StudioPicture, StudioTurn } from '@/api/shared/studio'
import { formatBeijingTime } from '@/utils/beijing-time'
import StudioAttachments from './StudioAttachments.vue'
import StudioAssetImage from './StudioAssetImage.vue'
import StudioProcess from './StudioProcess.vue'
import StudioOutputs from './StudioOutputs.vue'
import StudioRevisionDetails from './StudioRevisionDetails.vue'
import { historicalRevisions } from './studio-revisions'
const history = ref<StudioTurn>()
const props = defineProps<{ turns: StudioTurn[]; transcript: Transcript[]; conversationId?: string | null; selected: string[]; disabled: boolean; scrollPosition?: number | null; hideEmptyGuide?: boolean; hideSkillLabels?: boolean; simplePictures?: boolean; batchAnnotation?: boolean }>()
const emit = defineEmits<{ 'scroll-position': [position: number, conversationId?: string | null]; failure: [reason: unknown]; group: [pictures: StudioPicture[]]; toggle: [id: string]; modify: [picture: StudioPicture]; 'batch-modify': [pictures: StudioPicture[]] }>()
const labels: Record<string, string> = { queued: '排队中', running: '执行中', collecting: '收取结果中', cancelling: '正在停止', uncertain: '执行状态待核实', succeeded: '已回复', partial: '已回复', failed: '执行失败', cancelled: '已停止' }
function deliveryProgress(turn: StudioTurn) {
  const delivery = turn.deliveryStatus
  if (!delivery || delivery.state === 'complete') return ''
  if (delivery.state === 'capturing') return '回复已结束，正在接收文件'
  if (delivery.state === 'partial' || delivery.state === 'waiting') return `文件收取已结束，已保存 ${delivery.saved}${delivery.expected === null ? ' 个' : `/${delivery.expected} 个`}。未保存的文件可通过“取回文件”重试。`
  return `回复已结束，文件保存中 ${delivery.saved}${delivery.expected === null ? ' 个' : `/${delivery.expected}`}`
}
const byTurn = computed(() => {
  const result = new Map<string, Transcript[]>()
  for (const entry of props.transcript) { const items = result.get(entry.turnId) || []; items.push(entry); result.set(entry.turnId, items) }
  return result
})
function replyTime(turn: StudioTurn) {
  const reply = turn.reply || byTurn.value.get(turn.id)?.findLast(entry => entry.kind === 'message')?.text
  if (!reply?.trim()) return ''
  const time = formatBeijingTime(turn.replyTimeSource ? turn.replyAt : null, '时间未记录')
  return turn.replyTimeSource === 'completed' && time !== '时间未记录' ? `完成于 ${time}` : time
}
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
