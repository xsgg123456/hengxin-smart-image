<template>
  <article class="studio-message assistant" :data-turn="turn.id">
    <div class="studio-message-name">Codex <small>{{ labels[turn.status] }}</small></div>
    <div class="studio-bubble">
      <details class="studio-execution process-group" :open="open" @toggle="syncOpen">
        <summary>
          <span>{{ turn.status === 'running' ? '正在执行' : '执行过程' }}</span>
          <span class="process-meta">{{ turn.status === 'succeeded' ? '已完成' : labels[turn.status] }} · {{ turn.entries.length }} 条记录</span>
          <span class="process-toggle">{{ open ? '收起' : '展开查看' }}</span>
        </summary>
        <div class="process-content"><StudioTranscript :entries="turn.entries" :running="turn.status === 'running'" /></div>
      </details>
      <template v-if="turn.status === 'succeeded'">
        <StudioMarkdown :text="turn.reply" />
        <div class="studio-selection-bar"><ElCheckbox :model-value="turn.pictures.every(p => selected.includes(p.id))" :indeterminate="turn.pictures.some(p => selected.includes(p.id)) && !turn.pictures.every(p => selected.includes(p.id))" @change="$emit('group', turn.pictures)">全选本组</ElCheckbox><span>已选 {{ turn.pictures.filter(p => selected.includes(p.id)).length }} / {{ turn.pictures.length }} 张</span></div>
        <div class="studio-pictures">
          <div v-for="picture in turn.pictures" :key="picture.id" class="studio-picture" :class="{ selected: selected.includes(picture.id) }">
            <AssetImage :asset="picture" :group="turn.pictures" title="本轮产物 · 示例图片" />
            <div class="studio-picture-footer"><ElCheckbox :model-value="selected.includes(picture.id)" @change="$emit('toggle', picture.id)">{{ picture.name }}</ElCheckbox><ElButton text size="small" type="primary" @click="$emit('modify', picture)">修改这张</ElButton><small v-if="archived.includes(picture.id)">已归档 · 预览</small></div>
          </div>
        </div>
      </template>
      <ElAlert v-else-if="turn.status === 'failed'" title="本轮执行失败，尚未输出最终结果。已保留执行过程，可继续补充要求后重试。（示例）" type="error" :closable="false" />
      <ElAlert v-else-if="turn.status === 'cancelled'" title="本轮已停止，尚未输出最终结果。已保留收到的过程内容。（示例）" type="warning" :closable="false" />
    </div>
  </article>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import StudioTranscript from '@/views/overseas/studio/StudioTranscript.vue'
import StudioMarkdown from '@/views/overseas/studio/StudioMarkdown.vue'
import AssetImage from '../preview-studio-images/AssetImage.vue'
import type { Asset } from '../preview-studio-images/state'
import type { PreviewTurn } from './fixtures'
const props = defineProps<{ turn: PreviewTurn; selected: string[]; archived: string[] }>()
defineEmits<{ group: [pictures: Asset[]]; toggle: [id: string]; modify: [asset: Asset] }>()
const labels = { running: '执行中', succeeded: '已回复', failed: '执行失败', cancelled: '已停止' }
const open = ref(props.turn.status !== 'succeeded')
watch(() => props.turn.status, status => { open.value = status !== 'succeeded' })
function syncOpen(event: Event) { open.value = (event.target as HTMLDetailsElement).open }
</script>
