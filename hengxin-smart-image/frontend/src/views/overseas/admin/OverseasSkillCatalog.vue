<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h2>海外 Skill 目录</h2><p>查看已安装 Skill，AI 设计工作台使用相同目录。</p></div><ElButton :loading="loading" @click="$emit('refresh')">刷新 Skill</ElButton></div>
    <div class="hx-filter"><ElInput v-model="search" class="hx-search" aria-label="搜索 Skill" placeholder="搜索名称或描述" clearable /></div>
    <p v-if="loading" role="status">正在加载 Skill 目录…</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <ArtTable v-else :data="rows" :columns="columns" :cell-style="{ verticalAlign: 'top' }" :loading="loading" height="auto" empty-height="280px" :show-table-header="false" :show-pagination="false" :empty-text="search.trim() ? '暂无匹配的 Skill，请调整搜索' : '暂无已安装 Skill'">
      <template #displayName="{ row }"><span class="skill-text">{{ row.displayName }}</span></template>
      <template #description="{ row }"><span class="skill-text">{{ row.description || '暂无描述' }}</span></template>
    </ArtTable>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import type { Skill } from '@/api/overseas/management'
const props = defineProps<{ skills: Skill[]; loading?: boolean; error?: string }>()
defineEmits<{ refresh: [] }>()
const search = ref('')
const rows = computed(() => props.skills.filter(s => [s.displayName, s.name, s.description].some(value => value.toLowerCase().includes(search.value.trim().toLowerCase()))))
const columns = [{ prop: 'displayName', label: '名称', minWidth: 100, useSlot: true }, { prop: 'description', label: '描述', minWidth: 140, useSlot: true }]
</script>
<style scoped>
.skill-text { display: block; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
.hx-admin-section-head { flex-wrap: wrap; }
.hx-admin-section-head > div { min-width: 0; }
.hx-admin-table-card { min-width: 0; }
</style>
