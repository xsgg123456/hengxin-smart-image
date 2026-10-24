<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="polish-switch"><ElButtonGroup><ElButton :type="page === 'create' ? 'primary' : 'default'" @click="page = 'create'">提交图需预览</ElButton><ElButton :type="page === 'studio' ? 'primary' : 'default'" @click="page = 'studio'">AI 设计工作台预览</ElButton></ElButtonGroup><span>交互预览 · 示例数据</span><ElSwitch v-if="page === 'studio'" v-model="baseline" active-text="对照原版" /></div>
    <div v-if="page === 'create'" class="hx-page"><CreatePreview v-model="draft" allowed @back="page = 'studio'"><template #designer><ElFormItem label="负责设计" required><ElSelect v-model="designer"><ElOption value="张帅" /></ElSelect></ElFormItem></template></CreatePreview></div>
    <div v-else class="hx-page">
      <div class="hx-heading"><div><h1>{{ task.name }}</h1><p>{{ task.productName }} · {{ task.brand }} · 亚马逊/Amazon · 美国站 · 负责设计：张帅</p></div></div>
      <StudioPreview actor-id="" :task="task" :baseline="baseline" @failure="explain" />
    </div>
  </OverseasShell>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import CreatePreview from './CreatePreview.vue'
import StudioPreview from './StudioPreview.vue'
import { task } from './preview-api'
const page = ref('studio'), baseline = ref(false), designer = ref('张帅')
const draft = ref({ name: '', productName: '', brand: '', platform: 'Amazon', market: '', remarks: '', skus: [{ code: '' }] })
function explain() { ElMessage.info('当前为独立界面预览，不连接真实业务。') }
</script>
