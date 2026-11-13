<template>
  <OverseasActivityPage v-if="page === 'activity'" :api="api" :all-members="allMembers" @failure="$emit('failure',$event)" />
  <OverseasLiveActivity v-else-if="page === 'usage' || page === 'monitor'" :key="page" :page="page" :api="api" :all-members="allMembers" @failure="$emit('failure',$event)" />
  <OverseasLiveSkills v-else-if="page === 'skills'" :api="api" :transfer-api="skillTransfers" @failure="$emit('failure',$event)" />
  <OverseasLiveSettings v-else-if="page === 'settings'" :api="api" @failure="$emit('failure',$event)" />
</template>
<script setup lang="ts">
import { type ManagementApi, type ManagementPage } from '@/api/overseas/management'
import OverseasLiveActivity from './OverseasLiveActivity.vue'
import OverseasActivityPage from './OverseasActivityPage.vue'
import OverseasLiveSkills from '@/views/shared/skills/OverseasLiveSkills.vue'
import { createSkillTransferApi } from '@/api/overseas/skill-transfers'
import OverseasLiveSettings from './OverseasLiveSettings.vue'
defineProps<{page:ManagementPage;api:ManagementApi;allMembers?:boolean}>()
defineEmits<{failure:[reason:unknown]}>()
const skillTransfers = createSkillTransferApi()
</script>
