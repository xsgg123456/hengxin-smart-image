<template>
  <div class="folder-actions">
    <ElButton text size="small" :loading="busy === 'save'" :disabled="!!busy || disabled" @click="saveFolder">保存为文件夹</ElButton>
    <ElButton v-if="incomplete" text size="small" :disabled="!!busy || disabled" @click="retrySave">核验并重试保存</ElButton>
    <ElButton v-if="canManage" text type="danger" size="small" :loading="busy === 'delete'" :disabled="!!busy || disabled" @click="remove">删除 Skill</ElButton>
    <span v-if="status" role="status" class="folder-status">{{ status }}</span>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import type { ManagedSkill } from '@/api/overseas/management'
import { skillTransferError, type SkillTransferApi } from '@/api/overseas/skill-transfers'
import { chooseParent, prepareFolderSave, writeFolder, type FolderSave } from './skill-folder-save'
const props = defineProps<{ skill: ManagedSkill; api: SkillTransferApi; canManage: boolean; disabled?: boolean }>()
const emit = defineEmits<{ changed: []; failure: [reason: unknown] }>()
const busy = ref(''), status = ref(''), incomplete = ref(false)
let pending: FolderSave | undefined
async function write() {
  if (!pending) return
  try {
    await writeFolder(pending, props.api, (done, total) => { status.value = `已写入并核验 ${done}/${total} 项` })
    status.value = '文件夹保存完成，全部目录和文件已读回核验'; incomplete.value = false; pending = undefined
  } catch (reason) { incomplete.value = true; status.value = `文件夹不完整：${skillTransferError(reason)}。可在本页核验并重试保存`; emit('failure', reason) }
}
async function saveFolder() {
  if (busy.value || props.disabled) return
  busy.value = 'save'; status.value = ''
  try {
    // Request permission before any network await, while the user gesture is active.
    const parent = await chooseParent()
    const descriptor = await props.api.package(props.skill.id)
    pending = await prepareFolderSave(parent, props.skill.id, descriptor); incomplete.value = false
    await write()
  } catch (reason) {
    if (!(reason instanceof DOMException && reason.name === 'AbortError')) { status.value = skillTransferError(reason); emit('failure', reason) }
  } finally { busy.value = '' }
}
async function retrySave() { if (busy.value || props.disabled || !pending) return; busy.value = 'save'; try { await write() } finally { busy.value = '' } }
async function remove() {
  if (!props.canManage || busy.value || props.disabled) return
  busy.value = 'delete'; status.value = ''
  const version = props.skill.version
  let submitted = false
  try {
    const descriptor = await props.api.package(props.skill.id)
    try { await ElMessageBox.confirm(`删除「${props.skill.displayName}」后，该 Skill 将从所有平台及新轮选择中移除。已提交轮次和历史冻结版本保留，不影响排队、在途或重试任务。`, '删除 Skill', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }) } catch { return }
    submitted = true
    await props.api.remove(props.skill.id, descriptor.release, descriptor.checksum, version)
    status.value = 'Skill 已删除，历史冻结版本保留'; emit('changed')
  } catch (reason) {
    if (submitted && (!(reason instanceof IdentityError) || reason.status === 0 || reason.status >= 500)) {
      try { await props.api.package(props.skill.id) }
      catch (check) {
        if (check instanceof IdentityError && check.status === 404) { status.value = '已核实 Skill 已删除，历史冻结版本保留'; emit('changed'); return }
        status.value = `删除结果尚未确认，请刷新目录核对：${skillTransferError(check)}`; emit('failure', check); return
      }
    }
    status.value = skillTransferError(reason); emit('failure', reason)
    if (reason instanceof IdentityError && reason.status === 409) emit('changed')
  }
  finally { busy.value = '' }
}
</script>
<style scoped>
.folder-actions { display:flex; flex-direction:column; align-items:flex-start; gap:8px; min-width:0; }
.folder-actions .el-button { margin-left:0; max-width:100%; }
.folder-status { font-size:12px; line-height:1.6; overflow-wrap:anywhere; }
</style>
