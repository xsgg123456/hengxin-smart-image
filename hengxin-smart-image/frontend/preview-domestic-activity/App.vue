<template>
  <OverseasShell>
    <template #account><span class="hx-demo-badge">交互预览 · 示例数据</span><ElAvatar :size="32">张</ElAvatar><ElButton text type="primary" @click="explain">切换业务</ElButton><ElButton text type="primary" @click="explain">退出登录</ElButton></template>
    <div class="preview-tools"><span>国内管理中心 · 合并方案预览</span><div><ElSelect v-model="scene" aria-label="预览场景" size="small" :disabled="baseline" style="width:125px"><ElOption v-for="(label,key) in scenes" :key="key" :label="label" :value="key" /></ElSelect><ElButton size="small" :type="route.path.endsWith('/usage') ? 'primary' : 'default'" @click="router.push('/management/usage')">原版调用统计</ElButton><ElButton size="small" :type="route.path.endsWith('/monitor') ? 'primary' : 'default'" @click="router.push('/management/monitor')">原版执行监控</ElButton><ElButton v-if="baseline" size="small" type="primary" @click="router.push('/management/activity')">返回合并版</ElButton></div></div>
    <ArtPageContent />
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import ArtPageContent from '@/components/core/layouts/art-page-content/index.vue'
import { scene, scenes } from './data'
const route = useRoute(), router = useRouter()
const baseline = computed(() => ['/management/usage', '/management/monitor'].includes(route.path))
function explain() { ElMessage.info('当前为独立预览，未连接真实业务。') }
</script>
