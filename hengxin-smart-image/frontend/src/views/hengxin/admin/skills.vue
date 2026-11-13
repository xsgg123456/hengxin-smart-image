<template>
  <section class="hx-page">
    <div class="hx-heading"><div><span class="hx-admin-kicker">WORKFLOW SKILLS</span><h1>Skills 管理</h1><p>管理国内工作台的 Skill，用户在每轮发送前按需选择使用。</p></div><ElTag>仅超级管理员</ElTag></div>
    <ElCard shadow="never" class="art-card domestic-skills-card">
      <ElTabs v-model="tab"><ElTabPane label="Skill 目录" name="catalog" :disabled="bindingSaving" /><ElTabPane label="工作台绑定" name="bindings" /></ElTabs>
      <ElAlert v-if="tab === 'catalog' && bindingsError" :title="bindingsError" type="error" :closable="false"><ElButton @click="refreshBindings">重试</ElButton></ElAlert>
      <OverseasLiveSkills v-if="tab === 'catalog'" :api="api" :transfer-api="api.transfers" :domestic-bindings="bindings" :domestic-workspaces="domesticWorkspaces" domestic @failure="failure" @bindings="tab = 'bindings'" @bindings-refresh="refreshBindings" />
      <DomesticStudioBindings v-else :api="api" @failure="failure" @saved="bindingsSaved" @saving="bindingSaving = $event" />
    </ElCard>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { createDomesticStudioSkillsApi, type WorkspaceBindings } from '@/api/hengxin/domestic-studio-skills'
import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
import OverseasLiveSkills from '@/views/shared/skills/OverseasLiveSkills.vue'
import DomesticStudioBindings from './DomesticStudioBindings.vue'
const api = createDomesticStudioSkillsApi(), tab = ref('catalog')
const bindings = ref<WorkspaceBindings | null>(null), bindingsError = ref(''), bindingSaving = ref(false)
let bindingRequest = 0
async function refreshBindings() {
  const request = ++bindingRequest
  bindings.value = null; bindingsError.value = ''
  try { const value = await api.getBindings(); if (request === bindingRequest) bindings.value = value.bindings }
  catch (reason) { if (request === bindingRequest) { bindingsError.value = '无法加载工作台绑定，请重试'; failure(reason) } }
}
function bindingsSaved(value: WorkspaceBindings) { ++bindingRequest; bindings.value = value }
onMounted(refreshBindings)
watch(tab, value => { if (value === 'catalog') void refreshBindings() })
function failure(reason: unknown) { if (reason instanceof IdentityError && [401, 403].includes(reason.status)) ElMessage.error(reason.message) }
</script>
<style scoped>
.domestic-skills-card { margin-top:24px; }
</style>
