<template>
  <ElTooltip v-if="label" :disabled="state !== 'uncertain'" content="执行结果待核实，确认结束前不可删除任务" placement="top">
    <ElTag type="primary" size="small" class="cli-activity-tag">{{ label }}</ElTag>
  </ElTooltip>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { cliActivityLabel, type CliActivity } from '@/types/api-image-edits'
const props = defineProps<{ state?: CliActivity }>()
const label = computed(() => cliActivityLabel(props.state))
</script>
<style scoped>
.cli-activity-tag { margin:4px 0 4px 4px; flex-shrink:0; }
</style>
