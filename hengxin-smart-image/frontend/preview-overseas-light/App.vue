<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="preview-bar"><span>交互预览 · 示例数据</span><div><ElSelect v-model="scene" aria-label="预览场景" size="small" style="width:112px"><ElOption label="正常数据" value="normal" /><ElOption label="加载中" value="loading" /><ElOption label="空数据" value="empty" /><ElOption label="加载失败" value="error" /></ElSelect><ElSwitch v-model="baseline" aria-label="对照原版" active-text="对照原版" /></div></div>
    <div class="preview-content">
      <ActivityPreview v-show="page === 'activity'" :baseline="baseline" :scene="scene" @retry="scene = 'normal'" />
      <TasksPreview v-show="page === 'tasks'" :baseline="baseline" :scene="scene" @retry="scene = 'normal'" />
      <ArchivePreview v-show="page === 'archive'" :baseline="baseline" :scene="scene" @retry="scene = 'normal'" />
      <div v-if="page === 'other'" class="hx-page"><ElEmpty description="本次预览聚焦调用与执行、成品库、工作流任务"><ElButton type="primary" @click="router.push('/overseas/management/activity')">查看调用与执行</ElButton></ElEmpty></div>
    </div>
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import ActivityPreview from './ActivityPreview.vue'
import TasksPreview from './TasksPreview.vue'
import ArchivePreview from './ArchivePreview.vue'
const route = useRoute(), router = useRouter(), baseline = ref(false), scene = ref('normal')
const page = computed(() => route.path.endsWith('/activity') ? 'activity' : route.path.endsWith('/tasks') ? 'tasks' : route.path.endsWith('/archive') ? 'archive' : 'other')
watch(page, () => { scene.value = 'normal' })
function explain() { ElMessage.info('当前为独立交互预览，未连接真实业务。') }
</script>

