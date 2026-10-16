<template>
  <aside class="studio-materials">
    <div class="studio-materials-title"><strong>任务素材 · {{ assets.length }}</strong><ElButton text size="small" type="primary" @click="$emit('close')">收起</ElButton></div>
    <p class="studio-materials-note">勾选后引用，或拖入输入区。移除仅影响此列表，历史消息与已发送文件保留。</p>
    <ElCheckbox :model-value="selected.length === assets.length && !!assets.length" :indeterminate="!!selected.length && selected.length < assets.length" @change="selected = selected.length === assets.length ? [] : assets.map(a => a.id)">全选素材</ElCheckbox>
    <div class="studio-materials-list">
      <div v-for="asset in assets" :key="asset.id" class="studio-source-file" draggable="true" @dragstart="$event.dataTransfer?.setData('application/x-preview-material', asset.id)">
        <ElCheckbox :model-value="selected.includes(asset.id)" :aria-label="`选择 ${asset.name}`" @change="toggle(asset.id)" />
        <AssetImage v-if="asset.image" :asset="asset" :group="assets" title="任务素材" />
        <span v-else class="preview-doc-icon">文档</span>
        <div class="material-info"><span :title="asset.name">{{ asset.name }}</span><small>{{ asset.caption || '上传附件' }}</small><a :href="asset.url" :download="asset.name">下载原文件</a></div>
        <button class="material-remove" :aria-label="`从列表移除 ${asset.name}`" title="从列表移除" @click.stop="$emit('remove', asset)"><ElIcon><Delete /></ElIcon></button>
      </div>
    </div>
    <ElEmpty v-if="!assets.length" description="暂无任务素材" :image-size="50" />
    <div class="preview-demo-tools"><span>仅预览</span><ElButton text size="small" @click="$emit('duplicate')">演示重复上传</ElButton><ElButton text size="small" @click="$emit('reset')">重置</ElButton></div>
    <div class="studio-materials-bottom"><ElButton type="primary" :disabled="!selected.length" @click="$emit('add', assets.filter(a => selected.includes(a.id))); selected = []">引用所选素材（{{ selected.length }}）</ElButton></div>
  </aside>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import type { Asset } from './state'
import AssetImage from './AssetImage.vue'
const props = defineProps<{ assets: Asset[] }>()
defineEmits<{ close: []; add: [assets: Asset[]]; remove: [asset: Asset]; duplicate: []; reset: [] }>()
const selected = ref<string[]>([])
watch(() => props.assets, list => { selected.value = selected.value.filter(id => list.some(a => a.id === id)) })
function toggle(id: string) { selected.value = selected.value.includes(id) ? selected.value.filter(x => x !== id) : [...selected.value, id] }
</script>
