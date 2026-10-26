<template>
  <OverseasShell>
    <template #account>
      <ElTag>{{ businessNames[side] }}</ElTag><ElButton text @click="switchOpen = true">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton>
    </template>
    <div class="layout-content">
      <div class="auth-preview-bar">
        <ElTag type="info" effect="plain">交互预览</ElTag><span>示例数据 · 不连接真实账号和任务</span>
        <label for="auth-scenario">演示状态</label><ElSelect id="auth-scenario" :model-value="accounts[side].status" aria-label="演示状态" @change="changeScenario">
          <ElOption v-for="(label, value) in statusNames" :key="value" :value="value" :label="label" />
        </ElSelect><ElButton text @click="reset">重置演示</ElButton>
      </div>
      <AccountPage v-if="route.path.endsWith('/codex-auth')" :key="side + revision" :side="side" />
      <div v-else class="hx-page"><div class="hx-heading"><div><h1>{{ route.meta.title }}</h1></div></div><ElCard class="art-card hx-section"><ElEmpty description="此独立预览仅演示 Codex 账号配置"><ElButton type="primary" @click="go(side)">返回 Codex 账号</ElButton></ElEmpty></ElCard></div>
    </div>
    <ElDialog v-model="switchOpen" title="切换业务" width="min(480px, calc(100vw - 32px))" align-center>
      <p class="hx-muted">选择要查看的业务，两边账号配置独立。</p>
      <div class="auth-business-options"><ElButton v-for="(name,key) in businessNames" :key="key" :type="side === key ? 'primary' : 'default'" @click="go(key)">{{ name }}{{ side === key ? ' · 当前' : '' }}</ElButton></div>
    </ElDialog>
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import AccountPage from './AccountPage.vue'
import { accounts, businessNames, statusNames, scenario, type Business, type AccountStatus } from './model'
import { syncMenus } from './navigation'
const route = useRoute(), router = useRouter(), switchOpen = ref(false), revision = ref(0)
const side = computed<Business>(() => route.path.startsWith('/overseas') ? 'overseas' : 'domestic')
watch(() => route.path, () => syncMenus(side.value), { immediate: true })
function go(next: Business) { switchOpen.value = false; void router.push(next === 'domestic' ? '/management/codex-auth' : '/overseas/admin/codex-auth') }
function changeScenario(status: AccountStatus) { revision.value++; scenario(side.value, status) }
function reset() { changeScenario(side.value === 'domestic' ? 'expired' : 'ready') }
function explain() { ElMessage.info('当前为独立预览，没有登录真实业务。') }
</script>
