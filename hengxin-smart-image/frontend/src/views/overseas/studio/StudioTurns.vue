<template>
  <div class="studio-messages" aria-live="polite">
    <div v-if="!turns.length" class="studio-empty"><h2>从你的设计需求开始</h2><p>按需选择 Skill，引用任务素材，直接告诉 Codex 你想怎么做。</p></div>
    <template v-for="turn in turns" :key="turn.id">
      <article class="studio-message user"><div class="studio-message-name">设计师</div><div class="studio-bubble"><ElTag v-if="turn.skillName">{{ turn.skillName }}</ElTag><p>{{ turn.text }}</p><div class="studio-attachments"><ElButton v-for="asset in turn.attachments" :key="asset.id" size="small" @click="$emit('preview', asset)">{{ asset.name }}</ElButton></div><div v-if="turn.referencePictures.length" class="studio-attachments"><div v-for="(picture, index) in turn.referencePictures" :key="picture.id" class="studio-attachment"><ElImage :src="picture.url" :preview-src-list="turn.referencePictures.map(p => p.url)" :initial-index="index" preview-teleported fit="contain" /><span :title="picture.name">引用图片：{{ picture.name }}</span></div></div></div></article>
      <article class="studio-message assistant"><div class="studio-message-name">Codex <small>{{ labels[turn.status] || turn.status }}</small></div><div class="studio-bubble">
        <p v-if="turn.reply">{{ turn.reply }}</p><ElAlert v-if="turn.error" :title="turn.error" type="error" :closable="false" />
        <details v-if="events.some(e => e.turnId === turn.id)"><summary>执行消息</summary><p v-for="event in events.filter(e => e.turnId === turn.id)" :key="event.id">{{ event.text }}</p></details>
        <div v-if="turn.pictures.length" class="studio-selection-bar"><ElCheckbox :model-value="turn.pictures.every(p => selected.includes(p.id))" :indeterminate="turn.pictures.some(p => selected.includes(p.id)) && !turn.pictures.every(p => selected.includes(p.id))" :disabled="disabled" @change="$emit('group', turn.pictures)">全选本组</ElCheckbox><span>已选 {{ turn.pictures.filter(p => selected.includes(p.id)).length }} / {{ turn.pictures.length }} 张</span></div>
        <div class="studio-pictures"><div v-for="(picture, index) in turn.pictures" :key="picture.id" class="studio-picture" :class="{ selected: selected.includes(picture.id) }">
          <ElImage :src="picture.url" :preview-src-list="turn.pictures.map(p => p.url)" :initial-index="index" preview-teleported fit="contain" />
          <div class="studio-picture-footer"><ElCheckbox :model-value="selected.includes(picture.id)" :disabled="disabled" @change="$emit('toggle', picture.id)">{{ picture.name }}</ElCheckbox><ElButton text size="small" type="primary" :disabled="disabled" @click="$emit('modify', picture)">修改这张</ElButton><span v-if="picture.archived">已归档 · {{ picture.sku }}</span></div>
        </div></div>
      </div></article>
    </template>
  </div>
</template>
<script setup lang="ts">
import type { Asset, StudioEvent, StudioPicture, StudioTurn } from '@/api/overseas/studio'
defineProps<{ turns: StudioTurn[]; events: StudioEvent[]; selected: string[]; disabled: boolean }>()
defineEmits<{ preview: [asset: Asset]; group: [pictures: StudioPicture[]]; toggle: [id: string]; modify: [picture: StudioPicture] }>()
const labels: Record<string, string> = { queued: '排队中', running: '执行中', collecting: '收取结果中', cancelling: '正在停止', uncertain: '执行状态待核实', succeeded: '已回复', failed: '执行失败', cancelled: '已停止' }
</script>
