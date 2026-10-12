<template>
  <OverseasLiveActivity v-if="page === 'usage' || page === 'monitor'" :key="page" :page="page" :api="api" @failure="$emit('failure',$event)" />
  <OverseasLiveSkills v-else-if="page === 'skills'" :api="api" @failure="$emit('failure',$event)" />
  <OverseasLiveSettings v-else-if="page === 'settings'" :api="api" @failure="$emit('failure',$event)" />
</template>
<script setup lang="ts">
import { type ManagementApi, type ManagementPage } from '@/api/overseas/management'
import OverseasLiveActivity from './OverseasLiveActivity.vue'
import OverseasLiveSkills from './OverseasLiveSkills.vue'
import OverseasLiveSettings from './OverseasLiveSettings.vue'
defineProps<{page:ManagementPage;api:ManagementApi}>()
defineEmits<{failure:[reason:unknown]}>()
</script>
