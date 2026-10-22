<template>
  <OverseasSkillCatalog :skills="skills" :loading="loading" :error="error" :managed="true" :can-toggle="canToggle" :saving-id="savingId" :notice="notice" @refresh="load" @toggle="toggle" />
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { managementError, type ManagedSkill, type SkillCatalog, type ManagementApi } from '@/api/overseas/management'
import OverseasSkillCatalog from './OverseasSkillCatalog.vue'
const props = defineProps<{ api: Pick<ManagementApi, 'skills' | 'setSkillAvailability'> }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const skills = ref<ManagedSkill[]>([]), error = ref(''), loading = ref(false)
const canToggle = ref(false), savingId = ref(''), notice = ref('')
let active = true
function apply(result: SkillCatalog) { skills.value = result.items; canToggle.value = result.canToggle }
async function load() {
  if (loading.value || savingId.value) return
  loading.value = true; error.value = ''; notice.value = ''
  try { const result = await props.api.skills(); if (active) apply(result) }
  catch (reason) {
    if (!active) return
    skills.value = []; canToggle.value = false; error.value = managementError(reason)
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally { if (active) loading.value = false }
}
async function toggle(id: string) {
  if (!canToggle.value || loading.value || savingId.value) return
  const skill = skills.value.find(item => item.id === id)
  if (!skill) return
  savingId.value = id; notice.value = ''; error.value = ''
  try {
    const result = await props.api.setSkillAvailability(id, !skill.enabled, skill.version)
    if (active) { apply(result); notice.value = 'Skill 状态已更新' }
  } catch (reason) {
    if (!active) return
    if (reason instanceof IdentityError && reason.status === 401) {
      skills.value = []; canToggle.value = false; error.value = managementError(reason); emit('failure', reason)
    } else if (reason instanceof IdentityError && reason.status === 403) {
      canToggle.value = false; notice.value = '仅指定账号可调整 Skill，当前账号没有切换权限'
    } else {
      // Refresh conflicts and unknown responses before another write; never update optimistically.
      canToggle.value = false
      try {
        const result = await props.api.skills()
        if (active) {
          apply(result)
          notice.value = reason instanceof IdentityError && reason.status === 409
            ? 'Skill 状态已变化，已刷新最新状态，请核对后重新操作'
            : '切换结果未确认，已刷新服务端状态，请核对后重试'
        }
      } catch (refreshReason) {
        if (active) { error.value = `无法确认最新 Skill 状态，请刷新后重试：${managementError(refreshReason)}`; canToggle.value = false }
        if (active && refreshReason instanceof IdentityError && [401, 403].includes(refreshReason.status)) { skills.value = []; emit('failure', refreshReason) }
      }
    }
  } finally { if (active) savingId.value = '' }
}
onMounted(load)
onUnmounted(() => { active = false; skills.value = [] })
</script>
