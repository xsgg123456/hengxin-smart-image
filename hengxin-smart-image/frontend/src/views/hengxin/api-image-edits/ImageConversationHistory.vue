<template>
  <details class="conversation-history">
    <summary>修改过程与历史 · {{ conversation?.turns.length || 0 }} 轮 <span>{{ connection }}</span></summary>
    <div class="history-content">
      <div class="history-versions"><span>已发布版本</span><ElButton v-for="version in versions" :key="version.number" size="small" :disabled="disabled" @click="$emit('selectVersion', version.number)">基于 V{{ version.number }} 继续</ElButton></div>
      <p v-if="!conversation?.turns.length" class="hx-footnote">尚无修改轮次。提交后将在这里显示公开回复及结果。</p>
      <details v-for="(turn, index) in conversation?.turns" :key="turn.id" class="history-turn">
        <summary>第 {{ index + 1 }} 轮 · {{ editTurnLabels[turn.status] }}{{ turn.adoptedVersion ? ` · V${turn.adoptedVersion}` : '' }}</summary>
        <pre>{{ turn.text }}</pre>
        <p v-for="(message, i) in turn.messages" :key="i" class="message">{{ message }}</p>
        <ElAlert v-if="turn.error" :title="turn.error" type="error" :closable="false" />
        <RevisionReferences :references="turnPictures(turn)" />
        <ElButton v-if="turn.candidate" size="small" :disabled="disabled" @click="$emit('selectTurn', turn.id)">基于第 {{ index + 1 }} 轮候选继续</ElButton>
        <details><summary>本轮图片修改提示词</summary><pre>{{ turn.prompt }}</pre></details>
      </details>
    </div>
  </details>
</template>
<script setup lang="ts">
import type { ApiVersion } from '@/types/api-image-edits'
import type { EditConversation, EditTurn } from '@/types/api-image-conversation'
import { editTurnLabels } from '@/types/api-image-conversation'
import type { RevisionReference } from './revision-references'
import RevisionReferences from './RevisionReferences.vue'
defineProps<{ conversation?: EditConversation; versions: ApiVersion[]; connection: string; disabled?: boolean }>()
defineEmits<{ selectVersion: [number: number]; selectTurn: [id: string] }>()
function turnPictures(turn: EditTurn): RevisionReference[] {
  return [{ picture: turn.basePicture, name: '本轮底图', role: '本轮冻结的编辑基础' }, { picture: turn.annotation, name: '本轮标注', role: '仅用于定位' }, { picture: turn.candidate, name: '本轮候选', role: '采用后才替换当前成品' }].flatMap(value => value.picture ? [{ ...value, picture: value.picture }] : [])
}
</script>
<style scoped>
.conversation-history { margin:10px 0; font-size:13px; } summary { cursor:pointer; line-height:1.8; } summary span { margin-left:12px; color:var(--el-text-color-secondary); }
.history-content { max-height:36dvh; overflow:auto; padding:10px; border:1px solid var(--el-border-color); border-radius:8px; } .history-versions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.history-turn { margin-top:12px; border-top:1px solid var(--el-border-color-lighter); padding-top:8px; } pre,.message { white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; }
</style>

