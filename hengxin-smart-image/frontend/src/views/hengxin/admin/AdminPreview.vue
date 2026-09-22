<template>
  <template v-if="isMockMode">
    <ElAlert class="hx-admin-banner" :title="isDemoMode ? '框架 Demo · 管理数据保存在本机浏览器，未连接真实后台。' : '前端模拟预览 · 统计、健康、安装及配置均为演示数据。'" type="warning" :closable="false" show-icon />
    <div class="hx-admin-toolbar hx-gap">
      <div class="hx-admin-toolbar-copy"><span class="hx-admin-kicker">PREVIEW CONTROLS</span><span>{{ isDemoMode ? '角色共用当前场景数据，切换场景后独立保存。' : '切换后刷新页面，便于复现不同状态。' }}</span></div>
      <div class="hx-admin-toolbar-actions">
      <ElSelect :model-value="role" aria-label="预览角色" style="width: 190px" @change="value => change('role', value)"><ElOption v-for="item in roles" :key="item.value" :value="item.value" :label="item.label" /></ElSelect>
      <ElSelect :model-value="scenario" aria-label="管理模拟场景" style="width: 210px" @change="value => change('managementScenario', value)"><ElOption v-for="item in scenarios" :key="item.value" :value="item.value" :label="item.label" /></ElSelect>
      <DemoReset v-if="isDemoMode" />
      </div>
    </div>
  </template>
</template>
<script setup lang="ts">
import { isMockMode, isDemoMode } from '@/api/hengxin/client'
import DemoReset from '../components/DemoReset.vue'
const params = new URLSearchParams(window.location.search)
const role = params.get('role') || 'operator', scenario = params.get('managementScenario') || 'default'
const roles = [{ value: 'super_admin', label: '超级管理员' }, { value: 'design_manager', label: '设计主管' }, { value: 'designer', label: '设计人员' }, { value: 'operator', label: '运营人员' }]
const scenarios = [{ value: 'default', label: '常规预览' }, { value: 'empty', label: '空数据' }, { value: 'list-error', label: '读取失败与重试' }, { value: 'save-error', label: '保存失败与重试' }, { value: 'install-error', label: 'Skill同步失败与重试' }, { value: 'idle', label: '执行器空闲' }, { value: 'unknown', label: '状态未知 / Skill需选类型' }, { value: 'unavailable', label: '存储不可达' }, { value: 'worker-lost', label: 'Worker 失联' }, { value: 'auth-rejected', label: 'CLI 认证拒绝' }, { value: 'rate-limited', label: '执行限流' }, { value: 'timeout', label: '执行超时' }]
function change(key: string, value: string) { const url = new URL(window.location.href); url.searchParams.set(key, value); window.location.assign(url.href) }
</script>
