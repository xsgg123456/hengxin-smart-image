<template>
  <template v-if="isMockMode">
    <ElAlert title="前端模拟预览 · 统计、健康、安装及配置均为演示数据，未连接真实后台。" type="warning" :closable="false" show-icon />
    <div class="hx-filter hx-gap">
      <ElSelect :model-value="role" aria-label="预览角色" style="width: 190px" @change="value => change('role', value)"><ElOption v-for="item in roles" :key="item.value" :value="item.value" :label="item.label" /></ElSelect>
      <ElSelect :model-value="scenario" aria-label="管理模拟场景" style="width: 210px" @change="value => change('managementScenario', value)"><ElOption v-for="item in scenarios" :key="item.value" :value="item.value" :label="item.label" /></ElSelect>
      <span class="hx-muted">切换会刷新页面并重置模拟数据。</span>
    </div>
  </template>
</template>
<script setup lang="ts">
import { isMockMode } from '@/api/hengxin/client'
const params = new URLSearchParams(window.location.search)
const role = params.get('role') || 'operator', scenario = params.get('managementScenario') || 'default'
const roles = [{ value: 'super_admin', label: '超级管理员' }, { value: 'design_manager', label: '设计主管' }, { value: 'designer', label: '设计人员' }, { value: 'operator', label: '运营人员' }]
const scenarios = [{ value: 'default', label: '常规预览' }, { value: 'empty', label: '空数据' }, { value: 'list-error', label: '读取失败与重试' }, { value: 'save-error', label: '保存失败与重试' }, { value: 'install-error', label: '安装失败保留旧版' }, { value: 'idle', label: '执行器空闲' }, { value: 'unknown', label: '健康检查过期' }, { value: 'unavailable', label: '存储不可达' }, { value: 'worker-lost', label: 'Worker 失联' }, { value: 'auth-rejected', label: 'CLI 认证拒绝' }, { value: 'rate-limited', label: '执行限流' }, { value: 'timeout', label: '执行超时' }]
function change(key: string, value: string) { const url = new URL(window.location.href); url.searchParams.set(key, value); window.location.assign(url.href) }
</script>
