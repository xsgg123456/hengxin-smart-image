<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h2>海外 Skill 目录</h2><p>{{ managed ? '管理全部已安装 Skill，AI 设计工作台仅显示已开启项。' : '查看已安装 Skill 的名称与描述。' }}</p><p v-if="managed && !loading && !error && !canToggle">仅指定账号可调整，当前账号只读。</p></div><ElButton :loading="loading" :disabled="!!savingId" @click="$emit('refresh')">刷新 Skill</ElButton></div>
    <div class="hx-filter"><ElInput v-model="search" class="hx-search" aria-label="搜索 Skill" placeholder="搜索名称或描述" clearable /></div>
    <p v-if="loading" role="status">正在加载 Skill 目录…</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <ElAlert v-if="notice" :title="notice" type="info" :closable="false" class="hx-gap" />
    <ArtTable v-if="!error" :data="rows" :columns="columns" :cell-style="{ verticalAlign: 'top' }" :loading="loading" height="auto" empty-height="280px" :show-table-header="false" :show-pagination="false" :empty-text="search.trim() ? '暂无匹配的 Skill，请调整搜索' : '暂无已安装 Skill'">
      <template #displayName="{ row }"><span class="skill-text">{{ row.displayName }}</span></template>
      <template #description="{ row }"><span class="skill-text">{{ row.description || '暂无描述' }}</span></template>
      <template #availability="{ row }"><div class="skill-availability"><ElTag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '已开启' : '已关闭' }}</ElTag><ElButton v-if="canToggle" size="small" :aria-label="`${row.enabled ? '关闭' : '开启'} ${row.displayName}`" :loading="savingId === row.id" :disabled="loading || !!savingId" @click="$emit('toggle', row.id)">{{ row.enabled ? '关闭' : '开启' }}</ElButton></div></template>
    </ArtTable>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import type { Skill } from '@/api/overseas/management'
const props = defineProps<{ skills: Skill[]; loading?: boolean; error?: string; managed?: boolean; canToggle?: boolean; savingId?: string; notice?: string }>()
defineEmits<{ refresh: []; toggle: [id: string] }>()
const search = ref('')
const rows = computed(() => props.skills.filter(s => [s.displayName, s.name, s.description].some(value => value.toLowerCase().includes(search.value.trim().toLowerCase()))))
const columns = computed(() => [{ prop: 'displayName', label: '名称', minWidth: 80, useSlot: true }, { prop: 'description', label: '描述', minWidth: 120, useSlot: true }, ...(props.managed ? [{ prop: 'availability', label: '状态', width: 90, useSlot: true }] : [])])
</script>
<style scoped>
.skill-text { display: block; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
.hx-admin-section-head { flex-wrap: wrap; }
.hx-admin-section-head > div { min-width: 0; }
.hx-admin-table-card { min-width: 0; }
.skill-availability { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
</style>
