<template>
  <OverseasSkillCatalog :skills="skills" :loading="loading" :error="error" @refresh="load" />
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { managementError, type Skill, type ManagementApi } from '@/api/overseas/management'
import OverseasSkillCatalog from './OverseasSkillCatalog.vue'
const props = defineProps<{ api: Pick<ManagementApi, 'skills'> }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const skills = ref<Skill[]>([]), error = ref(''), loading = ref(false)
let active = true
async function load() {
  if (loading.value) return
  loading.value = true; error.value = ''
  try { const result = await props.api.skills(); if (active) skills.value = result.items }
  catch (reason) {
    if (!active) return
    skills.value = []; error.value = managementError(reason)
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally { if (active) loading.value = false }
}
onMounted(load)
onUnmounted(() => { active = false; skills.value = [] })
</script>
