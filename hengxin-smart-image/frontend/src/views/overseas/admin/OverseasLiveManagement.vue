<template>
  <OverseasActivityPage v-if="page === 'activity'" :api="api" :all-members="allMembers" @failure="$emit('failure',$event)" />
  <OverseasLiveActivity v-else-if="page === 'usage' || page === 'monitor'" :key="page" :page="page" :api="api" :all-members="allMembers" @failure="$emit('failure',$event)" />
  <ElTabs v-else-if="page === 'skills'" v-model="skillsTab">
    <ElTabPane label="Skill 目录" name="catalog">
      <OverseasLiveSkills v-if="skillsTab === 'catalog'" :api="api" :transfer-api="skillTransfers" @failure="$emit('failure',$event)" />
    </ElTabPane>
    <ElTabPane label="创作工具集工作台" name="bindings">
      <WorkspaceSkills v-if="skillsTab === 'bindings'" :api="api" @failure="$emit('failure',$event)" />
    </ElTabPane>
  </ElTabs>
  <OverseasLiveSettings v-else-if="page === 'settings'" :api="api" @failure="$emit('failure',$event)" />
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { type ManagementApi, type ManagementPage } from '@/api/overseas/management'
import OverseasLiveActivity from './OverseasLiveActivity.vue'
import OverseasActivityPage from './OverseasActivityPage.vue'
import OverseasLiveSkills from '@/views/shared/skills/OverseasLiveSkills.vue'
import { createSkillTransferApi } from '@/api/overseas/skill-transfers'
import OverseasLiveSettings from './OverseasLiveSettings.vue'
import WorkspaceSkills from './WorkspaceSkills.vue'
defineProps<{page:ManagementPage;api:ManagementApi;allMembers?:boolean}>()
defineEmits<{failure:[reason:unknown]}>()
const skillTransfers = createSkillTransferApi()
const skillsTab = ref('catalog')
</script>
