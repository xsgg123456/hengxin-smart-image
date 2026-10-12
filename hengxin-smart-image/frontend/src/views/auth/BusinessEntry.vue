<template>
  <div>
    <div class="business-options">
      <ElButton v-for="item in entries" :key="item.key"
        class="business-option" type="primary" plain
        :disabled="!mayEnter(identity, item.key)"
        :title="identity[item.key] ? item.label : label(item.key)"
        @click="emit('enter', item.key)">
        {{ item.label }}<span v-if="!identity[item.key]"> · {{ label(item.key) }}</span>
      </ElButton>
    </div>
    <ElButton class="hx-gap" :disabled="busy" text @click="emit('logout')">退出登录</ElButton>
  </div>
</template>
<script setup lang="ts">
import { mayEnter, type Business, type BusinessAccess } from '@/api/identity/access';
import type { AccessResult } from '@/api/identity/auth';
const props = defineProps<{ identity: BusinessAccess; states?: Partial<Record<Business, AccessResult>>; busy?: boolean }>();
function label(business: Business) { return props.busy ? '验证中' : props.states?.[business]?.state === 'error' ? '连接失败，请重试' : '暂无权限' }
const emit = defineEmits<{ enter: [business: Business]; logout: [] }>();
const entries: { key: Business; label: string }[] = [
  { key: 'domestic', label: '国内业务' }, { key: 'overseas', label: '海外业务' },
];
</script>
<style scoped>
.business-options { display: grid; gap: 20px; margin: 24px 0; }
.business-option { width: 100%; height: 64px; margin: 0; font-size: 18px; font-weight: 600; }
</style>
