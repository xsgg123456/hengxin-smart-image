<template>
  <OverseasArchiveFields :archive="{ ...task, taskName: task.name }" />
</template>
<script setup lang="ts">
import type { TaskDetail } from '@/api/overseas/tasks'
import OverseasArchiveFields from '../OverseasArchiveFields.vue'
defineProps<{ task: Pick<TaskDetail, 'name' | 'productName' | 'brand' | 'platform' | 'language' | 'skus'> }>()
</script>
