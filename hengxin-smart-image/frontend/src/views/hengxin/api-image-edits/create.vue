<template><component :is="page" /></template>
<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import { apiImageDemo } from '@/api/api-image-edits'
const page = defineAsyncComponent(() => apiImageDemo ? import('./DemoCreate.vue') : import('./RealCreate.vue'))
</script>
