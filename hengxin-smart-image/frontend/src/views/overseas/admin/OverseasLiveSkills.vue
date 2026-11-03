<template>
  <OverseasSkillCatalog :skills="skills" :transfer-api="transfers" @upload="uploadOpen = true" @failure="transferFailure" :loading="loading" :error="error" :managed="true" :can-toggle="canToggle" :saving-id="savingId" :notice="notice" :can-manage-platforms="canManagePlatforms" :platform-error="platformError" :save-platforms="savePlatforms" :refresh-platforms="load" @edit="platformError = ''" @refresh="load" @toggle="toggle" />
  <SkillFolderUpload v-if="canToggle" :open="uploadOpen" :api="transfers" @close="uploadOpen = false" @installed="load" @failure="transferFailure" />
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { managementError, type ManagedSkill, type SkillCatalog, type SkillPlatformUpdate, type ManagementApi } from '@/api/overseas/management'
import { createSkillTransferApi, type SkillTransferApi } from '@/api/overseas/skill-transfers'
import SkillFolderUpload from './SkillFolderUpload.vue'
import OverseasSkillCatalog from './OverseasSkillCatalog.vue'
const props = defineProps<{ api: Pick<ManagementApi, 'skills' | 'setSkillAvailability' | 'setSkillPlatforms'>; transferApi?: SkillTransferApi }>()
const transfers = props.transferApi || createSkillTransferApi()
const uploadOpen = ref(false)
const emit = defineEmits<{ failure: [reason: unknown] }>()
const skills = ref<ManagedSkill[]>([]), error = ref(''), loading = ref(false)
const canManagePlatforms = ref(false), platformError = ref('')
const canToggle = ref(false), savingId = ref(''), notice = ref('')
function transferFailure(reason: unknown) {
  if (reason instanceof IdentityError && reason.status === 401) { skills.value = []; canToggle.value = false; canManagePlatforms.value = false; emit('failure', reason) }
  if (reason instanceof IdentityError && reason.status === 403) { canToggle.value = false; notice.value = '当前账号没有此操作权限，请刷新目录核对权限' }
}
let active = true
function apply(result: SkillCatalog) { skills.value = result.items; canToggle.value = result.canToggle; canManagePlatforms.value = result.canManagePlatforms }
async function load() {
  if (loading.value || savingId.value) return
  loading.value = true; error.value = ''; notice.value = ''; platformError.value = ''
  try { const result = await props.api.skills(); if (active) apply(result) }
  catch (reason) {
    if (!active) return
    skills.value = []; canToggle.value = false; canManagePlatforms.value = false; error.value = managementError(reason)
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
      skills.value = []; canToggle.value = false; canManagePlatforms.value = false; error.value = managementError(reason); emit('failure', reason)
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
async function savePlatforms(items: SkillPlatformUpdate[]): Promise<boolean> {
  if (!canManagePlatforms.value || loading.value || savingId.value) return false
  savingId.value = 'platforms'; platformError.value = ''; notice.value = ''
  try {
    const result = await props.api.setSkillPlatforms(items)
    if (!active) return false
    apply(result); notice.value = '平台归属已更新'; return true
  } catch (reason) {
    if (!active) return false
    platformError.value = reason instanceof IdentityError && reason.status === 422 ? '平台设置不符合要求，请检查所选 Skill 和平台；你的草稿已保留' : managementError(reason)
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) {
      canManagePlatforms.value = false
      if (reason.status === 401) { skills.value = []; canToggle.value = false; emit('failure', reason) }
    } else if (!(reason instanceof IdentityError && reason.status === 422)) {
      canManagePlatforms.value = false
      try {
        const result = await props.api.skills()
        if (active) {
          apply(result)
          platformError.value = reason instanceof IdentityError && reason.status === 409
            ? '平台归属或开关已变化，已刷新最新版本；你的平台草稿和勾选已保留，请核对后重新保存'
            : '保存结果未确认，已刷新服务端状态；草稿和勾选已保留，请核对后重试'
        }
      } catch (refreshReason) {
        if (active) {
          platformError.value = `无法确认最新平台归属，请在弹窗内刷新最新目录后重试：${managementError(refreshReason)}`
          if (refreshReason instanceof IdentityError && [401, 403].includes(refreshReason.status)) emit('failure', refreshReason)
        }
      }
    }
    if (active) notice.value = platformError.value
    return false
  } finally { if (active) savingId.value = '' }
}
onMounted(load)
onUnmounted(() => { active = false; skills.value = [] })
</script>
