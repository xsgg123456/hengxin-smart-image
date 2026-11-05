<template>
  <div class="revision-details">
    <article v-for="item in items" :key="item.picture.id" class="revision-detail">
      <h3>修改 {{ item.picture.name }} <small>{{ item.marks.length }}处标注 · {{ item.references.length }}张参考图</small></h3>
      <div class="revision-detail-grid">
        <div class="revision-base"><ElImage :src="item.annotation || item.originalPreview || item.picture.url" :preview-src-list="[item.originalPreview || item.picture.url, ...(item.annotation ? [item.annotation] : [])]" fit="contain" preview-teleported :z-index="6500" /><small>{{ item.annotation ? '原图＋标注图 · 标记只用于定位' : '当前成品原图 · 修改基础' }}</small></div>
        <div><p class="revision-description">{{ item.text || '未添加位置标注，请在工作台输入区补充修改要求。' }}</p>
          <div v-for="(r, i) in item.references" :key="r.id" class="revision-reference"><ElImage :src="r.url" :alt="r.name" :preview-src-list="[r.url]" fit="contain" preview-teleported :z-index="6500" /><div style="overflow-wrap:anywhere;white-space:pre-wrap"><strong>参考图{{ i + 1 }} · {{ referenceLabel(r.kind, r.customPurpose) }}</strong><p>{{ r.note }}</p></div></div>
        </div>
      </div>
    </article>
  </div>
</template>
<script setup lang="ts">
import { referenceLabel, type PreparedRevision } from './state'
defineProps<{ items: PreparedRevision[] }>()
</script>
