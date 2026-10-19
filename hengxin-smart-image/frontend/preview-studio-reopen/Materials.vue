<template>
  <aside class="studio-materials">
    <div class="studio-materials-title"><strong>任务素材 · {{ assets.length }}</strong><ElButton text size="small" type="primary" @click="$emit('close')">收起</ElButton></div>
    <p class="studio-materials-note">勾选后引用，或拖入输入区。移除本轮附件不会删除原件。</p>
    <ElCheckbox :disabled="disabled" :model-value="selected.length === assets.length && !!assets.length" :indeterminate="!!selected.length && selected.length < assets.length" @change="selected = selected.length === assets.length ? [] : assets.map(a => a.id)">全选素材</ElCheckbox>
    <div class="studio-materials-list">
      <div v-for="asset in assets" :key="asset.id" class="studio-source-file" :draggable="!disabled" @dragstart="$event.dataTransfer?.setData('application/x-preview-material', asset.id)">
        <ElCheckbox :disabled="disabled" :model-value="selected.includes(asset.id)" :aria-label="`选择 ${asset.name}`" @change="toggle(asset.id)" />
        <AssetImage v-if="asset.image" :asset="asset" :group="assets" title="任务素材" />
        <span v-else class="preview-doc-icon">文档</span>
        <div class="material-info"><span :title="asset.name">{{ asset.name }}</span><small>{{ asset.caption || '上传附件' }}</small></div>
        <a :href="asset.url" :download="asset.name" :aria-label="`下载 ${asset.name}`" title="下载原文件" class="material-download">↓</a>
      </div>
    </div>
    <div class="studio-materials-bottom"><ElButton type="primary" :disabled="disabled || !selected.length" @click="$emit('add', assets.filter(a => selected.includes(a.id))); selected = []">引用所选素材（{{ selected.length }}）</ElButton></div>
  </aside>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import type { Asset } from '../preview-studio-images/state'
import AssetImage from '../preview-studio-images/AssetImage.vue'
defineProps<{ assets: Asset[]; disabled: boolean }>()
defineEmits<{ close: []; add: [assets: Asset[]] }>()
const selected = ref<string[]>([])
function toggle(id: string) { selected.value = selected.value.includes(id) ? selected.value.filter(x => x !== id) : [...selected.value, id] }
</script>
