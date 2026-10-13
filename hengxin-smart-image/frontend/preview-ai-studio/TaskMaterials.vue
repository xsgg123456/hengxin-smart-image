<template>
  <aside class="studio-materials" aria-label="任务素材">
    <div class="studio-materials-title"><strong>任务素材 <ElTag size="small">{{ taskMaterials.length }}</ElTag></strong><ElButton text size="small" @click="$emit('close')">收起</ElButton></div>
    <p class="studio-materials-note">来自前序图需 · 示例资料<br>拖到左侧输入区，或勾选后添加。</p>
    <div class="studio-materials-select"><ElCheckbox :model-value="checked.length === taskMaterials.length" :indeterminate="checked.length > 0 && checked.length < taskMaterials.length" @change="checked = checked.length === taskMaterials.length ? [] : taskMaterials.map(item => item.key)">全选素材</ElCheckbox><span>{{ checked.length }} / {{ taskMaterials.length }}</span></div>
    <div class="studio-materials-list">
      <div v-for="item in taskMaterials" :key="item.key" class="studio-source-file" draggable="true" @dragstart="startDrag($event, item.key)">
        <ElImage v-if="item.image" :src="item.url" :preview-src-list="[item.url]" preview-teleported fit="contain" />
        <button v-else class="studio-source-doc" @click="previewOpen = true"><Document /><span>TXT · 图需文档</span></button>
        <ElCheckbox :model-value="checked.includes(item.key)" @change="checked = checked.includes(item.key) ? checked.filter(key => key !== item.key) : [...checked, item.key]">{{ item.name }}</ElCheckbox>
      </div>
    </div>
    <div class="studio-materials-bottom"><ElButton type="primary" :disabled="!checked.length" @click="add">添加到本轮附件{{ checked.length ? `（${checked.length}）` : '' }}</ElButton><small>添加后可补充要求，再点击发送。</small></div>
    <ElDialog v-model="previewOpen" title="图需说明（示例）" width="min(560px, 92vw)" append-to-body><pre class="studio-brief-text">{{ brief }}</pre></ElDialog>
  </aside>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { taskMaterials } from './state'
import brief from './assets/task-brief.txt?raw'
const emit = defineEmits<{ close: []; add: [keys: string[]] }>()
const checked = ref<string[]>([]), previewOpen = ref(false)
function startDrag(event: DragEvent, key: string) { if (event.dataTransfer) { event.dataTransfer.setData('application/x-studio-material', key); event.dataTransfer.effectAllowed = 'copy' } }
function add() { emit('add', [...checked.value]); checked.value = [] }
</script>
