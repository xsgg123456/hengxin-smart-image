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
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import type { ManagedSkill } from '@/api/overseas/management'
import { skillTransferError, type SkillTransferApi } from '@/api/overseas/skill-transfers'
import { chooseParent, prepareFolderSave, writeFolder, type FolderSave } from './skill-folder-save'
const props = defineProps<{ skill: ManagedSkill; api: SkillTransferApi; canManage: boolean; disabled?: boolean }>()
const emit = defineEmits<{ changed: [notice?: string]; failure: [reason: unknown] }>()
const busy = ref(''), status = ref(''), incomplete = ref(false)
let pending: FolderSave | undefined
let pendingRemoval: { release: string; checksum: string; version: number } | undefined
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
  try {
    const version = props.skill.version
    const descriptor = pendingRemoval || { ...await props.api.package(props.skill.id), version }
    try { await ElMessageBox.confirm(`永久删除「${props.skill.displayName}」及不再需要的安装文件，并从所有平台及新轮选择中移除。历史会话资料保留。排队中或运行中的任务仍使用此 Skill 时无法删除，请稍后重试。`, '删除 Skill', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }) } catch { return }
    pendingRemoval = { release: descriptor.release, checksum: descriptor.checksum, version: descriptor.version }
    const result = await props.api.remove(props.skill.id, descriptor.release, descriptor.checksum, descriptor.version)
    pendingRemoval = undefined
    status.value = `Skill 已删除，释放 ${formatAttachmentSize(result.reclaimedBytes)}`; emit('changed', status.value)
  } catch (reason) {
    status.value = skillTransferError(reason); emit('failure', reason)
    if (reason instanceof IdentityError && reason.status === 409) { pendingRemoval = undefined; emit('changed') }
  }
  finally { busy.value = '' }
}
</script>
<style scoped>
.folder-actions { display:flex; flex-direction:column; align-items:flex-start; gap:8px; min-width:0; }
.folder-actions .el-button { margin-left:0; max-width:100%; }
.folder-status { font-size:12px; line-height:1.6; overflow-wrap:anywhere; }
</style>
