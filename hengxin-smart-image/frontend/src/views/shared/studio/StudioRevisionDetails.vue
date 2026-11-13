<template>
  <div class="revision-details">
    <article v-for="item in items" :key="item.base.id" class="revision-detail">
      <h3>修改 {{ item.base.name }} <small>{{ item.referenceImages?.length || 0 }}张参考图</small></h3>
      <div class="revision-detail-grid">
        <div class="revision-base"><StudioAssetImage :asset="item.annotation || item.base" :group="[item.base, ...(item.annotation ? [item.annotation] : [])]" title="修改原图与标注" @failure="$emit('failure', $event)" /><small>{{ item.annotation ? '原图＋标注图 · 标记只用于定位' : '当前成品原图 · 修改基础' }}</small></div>
        <div><p class="revision-description">{{ item.text || '未添加位置标注，请在工作台输入区补充修改要求。' }}</p>
          <div v-for="(r, i) in item.referenceImages || []" :key="r.asset.id" class="revision-reference"><StudioAssetImage :asset="r.asset" :group="(item.referenceImages || []).map(ref => ref.asset)" title="参考图" @failure="$emit('failure', $event)" /><div style="overflow-wrap:anywhere;white-space:pre-wrap"><strong>参考图{{ i + 1 }} · {{ referenceLabel(r.kind, r.customPurpose) }}</strong><p>{{ r.note }}</p></div></div>
        </div>
      </div>
    </article>
  </div>
</template>
<script setup lang="ts">
import type { StudioRevision } from './studio-revisions'
import { referenceLabel } from './editing/state'
import StudioAssetImage from './StudioAssetImage.vue'
defineProps<{ items: StudioRevision[] }>()
defineEmits<{ failure: [reason: unknown] }>()
</script>
