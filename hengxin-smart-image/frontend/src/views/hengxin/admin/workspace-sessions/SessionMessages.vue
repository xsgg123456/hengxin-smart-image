<template>
  <div ref="scroller" class="studio-messages wm-messages" @scroll="track" @load.capture="follow">
    <ElEmpty v-if="!turns.length" description="这个会话还没有提交消息" />
    <div v-else class="studio-conversation-divider">已提交的对话 · 北京时间</div>
    <template v-for="turn in turns" :key="turn.id">
      <article class="studio-message user"><div class="studio-message-name">{{ turn.actor?.name || ownerName || '姓名未记录' }}<small>{{ formatBeijingTime(turn.createdAt, '时间未记录') }}</small></div><div class="studio-bubble">
        <ElTag v-if="turn.skillName" size="small">{{ turn.skillName }}</ElTag><small v-else class="wm-subtext">本轮未选择 Skill</small><p>{{ turn.text }}</p>
        <div class="wm-assets"><ManagedAsset v-for="asset in [...turn.attachments, ...turn.referencePictures]" :key="asset.id" :asset="asset" @failure="$emit('failure', $event)" /></div>
        <details v-if="turn.imageEdits?.length" class="studio-execution"><summary>本轮修改材料（{{ turn.imageEdits.length }} 张）</summary><div v-for="edit in turn.imageEdits" :key="edit.pictureId"><strong>{{ pictureName(turn, edit.pictureId) }}</strong><p>{{ edit.text || '未添加位置说明' }}</p><p v-if="edit.annotationId">标注附件：{{ attachmentName(turn, edit.annotationId) }}</p><p v-for="reference in edit.references || []" :key="reference.attachmentId">{{ attachmentName(turn, reference.attachmentId) }} · {{ reference.kind === 'product' ? '产品参考' : reference.kind === 'effect' ? '效果参考' : reference.customPurpose }}：{{ reference.note }}</p></div></details>
      </div></article>
      <article class="studio-message assistant"><div class="studio-message-name">Codex <small>{{ labels[turn.status] || turn.status }}</small><small v-if="turn.replyAt">{{ formatBeijingTime(turn.replyAt, '时间未记录') }}</small></div><div class="studio-bubble">
        <StudioProcess :turn="turn" :entries="byTurn.get(turn.id) || []" />
        <p v-if="!turn.reply && !byTurn.get(turn.id)?.length" class="wm-muted">{{ ['queued', 'running'].includes(turn.status) ? '等待新的公开消息与执行记录…' : '没有可显示的公开回复或执行记录' }}</p>
        <ElAlert v-if="turn.error" :title="turn.error" type="error" :closable="false" /><ElAlert v-if="turn.deliveryError" :title="turn.deliveryError" type="warning" :closable="false" />
        <p v-if="turn.deliveryStatus && turn.deliveryStatus.state !== 'complete'" class="wm-subtext">文件保存状态：{{ deliveryLabels[turn.deliveryStatus.state] }} · 已保存 {{ turn.deliveryStatus.saved }}{{ turn.deliveryStatus.expected == null ? ' 个' : ` / ${turn.deliveryStatus.expected} 个` }}</p>
        <div class="wm-assets results"><ManagedAsset v-for="asset in [...turn.pictures, ...(turn.outputs || [])]" :key="asset.id" :asset="asset" @failure="$emit('failure', $event)" /></div>
      </div></article>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUpdate, onMounted, onUpdated, ref } from 'vue'
import type { StudioTranscript, StudioTurn } from '@/api/shared/studio'
import { formatBeijingTime } from '@/utils/beijing-time'
import StudioProcess from '@/views/shared/studio/StudioProcess.vue'
import ManagedAsset from './ManagedAsset.vue'
import { labels } from './presentation'
const props = defineProps<{ turns: StudioTurn[]; transcript: StudioTranscript[]; ownerName: string }>()
defineEmits<{ failure: [reason: unknown] }>()
const scroller = ref<HTMLElement>(); let nearBottom = true
function track() { const node = scroller.value; if (node) nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 64 }
function follow() { if (nearBottom && scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight }
onBeforeUpdate(track); onUpdated(follow); onMounted(follow)
const byTurn = computed(() => {
  const grouped = new Map<string, StudioTranscript[]>()
  for (const item of props.transcript) { const rows = grouped.get(item.turnId) || []; rows.push(item); grouped.set(item.turnId, rows) }
  return grouped
})
const pictureName = (turn: StudioTurn, id: string) => turn.referencePictures.find(item => item.id === id)?.name || '原图片不可用'
const attachmentName = (turn: StudioTurn, id: string) => turn.attachments.find(item => item.id === id)?.name || '附件不可用'
const deliveryLabels = { capturing: '正在收取', saving: '正在保存', waiting: '等待保存', partial: '部分保存' }
</script>
