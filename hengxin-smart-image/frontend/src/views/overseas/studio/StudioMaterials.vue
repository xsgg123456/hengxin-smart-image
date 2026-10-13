<template>
  <aside class="studio-materials">
    <div class="studio-materials-title"><strong>任务素材 · {{ assets.length }}</strong><ElButton text @click="$emit('close')">收起</ElButton></div>
    <p class="studio-materials-note">勾选后引用，或拖入输入区。移除本轮附件不会删除原件。</p>
    <ElCheckbox :model-value="all" :indeterminate="chosen.length > 0 && !all" :disabled="disabled" @change="chosen = all ? [] : assets.map(a => a.id)">全选素材</ElCheckbox>
    <ElEmpty v-if="!assets.length" description="暂无任务素材" :image-size="60" />
    <div class="studio-materials-list"><div v-for="asset in assets" :key="asset.id" class="studio-source-file" :draggable="!disabled" @dragstart="drag($event, asset.id)">
      <ElImage v-if="asset.contentType.startsWith('image/')" :src="asset.url" :preview-src-list="[asset.url]" preview-teleported fit="contain" />
      <button v-else class="studio-source-doc" @click="$emit('preview', asset)">查看资料</button>
      <ElCheckbox :model-value="chosen.includes(asset.id)" :disabled="disabled" :title="asset.name" @change="toggle(asset.id)">{{ asset.name }}</ElCheckbox>
    </div></div>
    <div class="studio-materials-bottom"><ElButton type="primary" :disabled="disabled || !chosen.length" @click="$emit('add', chosen)">引用所选素材（{{ chosen.length }}）</ElButton></div>
  </aside>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Asset } from '@/api/overseas/studio'
const props = defineProps<{ assets: Asset[]; disabled: boolean }>()
defineEmits<{ close: []; add: [ids: string[]]; preview: [asset: Asset] }>()
const chosen = ref<string[]>([]), all = computed(() => props.assets.length > 0 && chosen.value.length === props.assets.length)
watch(() => props.assets, assets => { chosen.value = chosen.value.filter(id => assets.some(a => a.id === id)) })
function toggle(id: string) { chosen.value = chosen.value.includes(id) ? chosen.value.filter(v => v !== id) : [...chosen.value, id] }
function drag(event: DragEvent, id: string) { event.dataTransfer?.setData('application/x-studio-material', id) }
</script>
