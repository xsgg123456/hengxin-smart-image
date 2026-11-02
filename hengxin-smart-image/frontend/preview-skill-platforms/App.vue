<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="layout-content"><div class="hx-page">
      <div class="preview-strip"><span>{{ previewNotice }}</span><div class="studio-actions"><ElButton size="small" :type="!studio ? 'primary' : 'default'" @click="router.push('/overseas/admin/skills')">Skill 管理预览</ElButton><ElButton size="small" :type="studio ? 'primary' : 'default'" @click="router.push('/overseas/tasks')">工作台筛选预览</ElButton></div></div>
      <template v-if="!studio">
        <div class="hx-heading"><div><h1>Skill 管理</h1><p>张帅 · 超级管理员</p></div><ElButton text @click="baseline = !baseline">{{ baseline ? '返回分组方案' : '对照现有页面' }}</ElButton></div>
        <OverseasSkillCatalog v-if="baseline" :skills="skills" managed can-toggle @refresh="explain" @toggle="toggle" />
        <Catalog v-else @studio="router.push('/overseas/tasks')" />
      </template>
      <StudioPreview v-else />
    </div></div>
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import OverseasSkillCatalog from '@/views/overseas/admin/OverseasSkillCatalog.vue'
import Catalog from './Catalog.vue'
import StudioPreview from './StudioPreview.vue'
import { skills, previewNotice } from './state'
const route = useRoute(), router = useRouter(), baseline = ref(false)
const studio = computed(() => route.path === '/overseas/tasks')
function explain() { ElMessage.info('此处为独立预览，请通过上方按钮体验 Skill 管理与工作台筛选。') }
function toggle(id: string) { const row = skills.find(s => s.id === id); if (row) row.enabled = !row.enabled }
</script>
<style scoped>
.preview-strip { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; margin:0 0 20px; color:var(--art-gray-500); font-size:12px; }
.hx-heading { margin-bottom:28px; }
</style>
