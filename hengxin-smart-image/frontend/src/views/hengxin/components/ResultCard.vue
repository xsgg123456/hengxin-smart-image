<template>
  <ElCard shadow="never" class="art-card">
    <ElImage v-if="picture" :src="picture.url" :alt="picture.name" :preview-src-list="[picture.url]" fit="contain" preview-teleported><template #error><ElEmpty description="图片加载失败，可重试下载" :image-size="50" /></template></ElImage>
    <ElEmpty v-else :description="slot.error ? '此位置生成失败' : `第 ${slot.slot + 1} 张 · ${state}`" :image-size="70" />
    <div class="hx-result-meta"><strong>第 {{ slot.slot + 1 }} 张{{ picture ? ` · ${picture.name}` : '' }}</strong></div>
    <ElSelect v-if="slot.versions.length" v-model="selected" aria-label="查看图片版本" class="hx-full">
      <ElOption v-for="version in slot.versions" :key="version.id" :value="version.id" :label="`v${version.version}${version.id === slot.currentVersionId ? ' · 当前版本' : ' · 历史版本'}`" />
    </ElSelect>
    <p v-if="picture && picture.id !== slot.currentVersionId" class="hx-footnote">正在查看历史版本，不改变当前结果。</p>
    <p v-if="slot.error" class="hx-muted">{{ slot.error }}{{ slot.currentVersionId ? '；旧结果已保留。' : '' }}</p>
    <div class="hx-row"><ElButton text type="primary" :disabled="!editable" @click="$emit('edit', slot.slot)">修改这张</ElButton><ElButton text :disabled="!picture || downloading" :loading="downloading" @click="download">{{ isMockMode ? '下载示例' : '下载图片' }}</ElButton></div>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ResultSlot, TaskState } from '@/types/hengxin'
import { isMockMode } from '@/api/hengxin/client'
import { downloadPicture } from '../download'
const props = defineProps<{ slot: ResultSlot; state: TaskState; editable: boolean }>()
defineEmits<{ edit: [slot: number] }>()
const selected = ref(''), downloading = ref(false)
watch(() => props.slot, (slot, previous) => {
  if (!slot.versions.some(v => v.id === selected.value) || selected.value === previous?.currentVersionId) selected.value = slot.currentVersionId || slot.versions[0]?.id || ''
}, { immediate: true })
const picture = computed(() => props.slot.versions.find(v => v.id === selected.value))
async function download() {
  if (!picture.value || downloading.value) return
  downloading.value = true
  try { await downloadPicture(picture.value) } finally { downloading.value = false }
}
</script>
