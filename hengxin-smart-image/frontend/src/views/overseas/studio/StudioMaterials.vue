<template>
  <aside class="studio-materials">
    <div class="studio-materials-title"><strong>任务素材 · {{ assets.length }}</strong><ElButton text @click="$emit('close')">收起</ElButton></div>
    <p class="studio-materials-note">勾选后引用，或拖入输入区。移除仅影响此列表，历史消息与已发送文件保留。</p>
    <ElCheckbox :model-value="all" :indeterminate="chosen.length > 0 && !all" :disabled="disabled" @change="chosen = all ? [] : assets.map(a => a.id)">全选素材</ElCheckbox>
    <ElEmpty v-if="!assets.length" description="暂无任务素材" :image-size="60" />
    <div class="studio-materials-list"><div v-for="asset in assets" :key="asset.id" class="studio-source-file" :data-material-id="asset.id" :draggable="!disabled" @dragstart="drag($event, asset.id)">
      <ElCheckbox :model-value="chosen.includes(asset.id)" :disabled="disabled" :aria-label="`选择 ${asset.name}`" @change="toggle(asset.id)" />
      <StudioAssetImage v-if="isImage(asset)" :asset="asset" :group="assets" title="任务素材" @failure="$emit('failure', $event)" />
      <span v-else class="studio-doc-icon">文件</span>
      <div class="material-info"><span :title="asset.name">{{ asset.name }}</span><small>{{ asset.source === 'task' ? '图需资料' : '上传附件' }} · {{ formatAttachmentSize(asset.sizeBytes) }}</small><AttachmentDownload :url="asset.url" :name="asset.name" @failure="$emit('failure', $event)" /></div>
      <button class="material-remove" :disabled="disabled" :aria-label="`从列表移除 ${asset.name}`" title="从列表移除" @click.stop="$emit('remove', asset)"><ElIcon><Delete /></ElIcon></button>
    </div></div>
    <div class="studio-materials-bottom"><ElButton type="primary" :disabled="disabled || !chosen.length" @click="$emit('add', chosen)">引用所选素材（{{ chosen.length }}）</ElButton><ElButton type="danger" plain :loading="removing" :disabled="disabled || !chosen.length" @click="$emit('removeSelected', [...chosen])">移除所选素材（{{ chosen.length }}）</ElButton></div>
  </aside>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import { isImage } from './studio-images'
import StudioAssetImage from './StudioAssetImage.vue'
import AttachmentDownload from '../AttachmentDownload.vue'
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import type { Asset } from '@/api/overseas/studio'
const props = defineProps<{ assets: Asset[]; disabled: boolean; removing?: boolean }>()
defineEmits<{ close: []; add: [ids: string[]]; remove: [asset: Asset]; removeSelected: [ids: string[]]; failure: [reason: unknown] }>()
const chosen = ref<string[]>([]), all = computed(() => props.assets.length > 0 && chosen.value.length === props.assets.length)
watch(() => props.assets, assets => { chosen.value = chosen.value.filter(id => assets.some(a => a.id === id)) })
function toggle(id: string) { chosen.value = chosen.value.includes(id) ? chosen.value.filter(v => v !== id) : [...chosen.value, id] }
function drag(event: DragEvent, id: string) { event.dataTransfer?.setData('application/x-studio-material', id) }
</script>
