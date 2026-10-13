<template>
  <div>
    <div class="business-options">
      <div v-for="item in entries" :key="item.key">
      <ElButton
        class="business-option" type="primary" plain
        :disabled="busy || !mayEnter(identity, item.key)"
        :title="identity[item.key] ? item.label : label(item.key)"
        @click="emit('enter', item.key)">
        {{ item.label }}<span v-if="!identity[item.key]"> · {{ label(item.key) }}</span>
      </ElButton>
      <p v-if="states?.[item.key]?.state === 'rejected' && applicationReason(item.key)" class="hx-footnote">拒绝原因：{{ applicationReason(item.key) }}</p>
      <ElButton v-if="canApply(item.key)" class="hx-gap" :disabled="busy" @click="emit('apply', item.key)">{{ states?.[item.key]?.state === 'rejected' ? '重新申请' : '申请' }}{{ item.key === 'domestic' ? '国内' : '海外' }}权限</ElButton>
      <ElButton v-if="states?.[item.key]?.state === 'pending'" class="hx-gap" :disabled="busy" @click="emit('withdraw', item.key)">撤回{{ item.key === 'domestic' ? '国内' : '海外' }}申请</ElButton>
      <ElButton v-if="states?.[item.key]?.state === 'error'" class="hx-gap" :disabled="busy" @click="emit('retry')">重试{{ item.label }}</ElButton>
      </div>
    </div>
    <ElButton class="hx-gap" :disabled="busy" text @click="emit('logout')">退出登录</ElButton>
  </div>
</template>
<script setup lang="ts">
import { mayEnter, type Business, type BusinessAccess } from '@/api/identity/access';
import type { AccessResult } from '@/api/identity/auth';
const props = defineProps<{ identity: BusinessAccess; states?: Partial<Record<Business, AccessResult>>; busy?: boolean }>();
const labels = { allowed: '', unregistered: '尚未加入', pending: '申请待审批', rejected: '申请被拒绝', disabled: '已停用，请联系本业务管理员', legacy_unconfirmed: '历史身份待核对，可明确申请', error: '连接失败，请重试' }
function label(business: Business) { const state = props.states?.[business]?.state; return props.busy ? '验证中' : state ? labels[state] : '暂无权限' }
function canApply(business: Business) { return ['unregistered', 'rejected', 'legacy_unconfirmed'].includes(props.states?.[business]?.state || '') }
function applicationReason(business: Business) { const state = props.states?.[business]; return state && 'application' in state ? state.application?.reason : '' }
const emit = defineEmits<{ enter: [business: Business]; apply: [business: Business]; withdraw: [business: Business]; retry: []; logout: [] }>();
const entries: { key: Business; label: string }[] = [
  { key: 'domestic', label: '国内业务' }, { key: 'overseas', label: '海外业务' },
];
</script>
<style scoped>
.business-options { display: grid; gap: 20px; margin: 24px 0; }
.business-option { width: 100%; min-height: 64px; height: auto; margin: 0; padding: 16px 12px; font-size: 18px; font-weight: 600; white-space: normal; }
.business-option :deep(span) { white-space: normal; line-height: 1.6; flex-wrap: wrap; }
</style>
