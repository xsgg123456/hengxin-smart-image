<template><DomesticWorkspace v-if="config && actor" :key="`${actor}:${config.key}`" :config="config" :actor="actor" /></template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
import DomesticWorkspace from './DomesticWorkspace.vue'
const route = useRoute(), user = useUserStore()
const config = computed(() => domesticWorkspaces.find(item => item.path === route.path))
const actor = computed(() => user.getUserInfo.userId ? String(user.getUserInfo.userId) : '')
</script>
