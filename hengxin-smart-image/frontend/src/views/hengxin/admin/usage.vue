<template><component :is="page" /></template>
<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import { isMockMode } from '@/api/hengxin/client'
const page = defineAsyncComponent(() => isMockMode ? import('./preview/UsagePreview.vue') : import('./ApiUsage.vue'))
</script>
