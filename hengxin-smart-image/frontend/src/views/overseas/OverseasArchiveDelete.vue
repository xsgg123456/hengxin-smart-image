<template>
  <div class="archive-delete">
    <ElButton v-if="canDelete" text type="danger" :loading="opening || sending" :disabled="status === 'deleting' || status === 'deleted'" @click="openDialog">{{ status === 'deleting' ? '正在删除' : status === 'delete_failed' ? '重试删除整套成品' : '删除整套成品' }}</ElButton>
    <p v-if="error && !open" role="alert">{{ error }}</p>
    <ElDialog v-model="open" title="永久删除整套成品" width="min(560px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!sending" :show-close="!sending">
      <p class="archive-delete-name">品名：{{ snapshot?.productName }}</p><p>图片数量：{{ snapshot?.pictureCount }} 张</p>
      <ElAlert title="整套归档图片、SKU及归档历史将永久删除，无法恢复。原工作流任务和原始资料保留。" type="warning" :closable="false" />
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <template #footer><ElButton :disabled="sending" @click="open = false">取消</ElButton><ElButton type="danger" :loading="sending" :disabled="!confirmed" @click="remove">确认删除</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import type { Archive, ArchiveDeletion, ArchivesApi } from '@/api/overseas/archives'
const props = defineProps<{ archive: Archive; canDelete: boolean; api: Pick<ArchivesApi, 'deletionPreview' | 'remove' | 'deletion'> }>()
const emit = defineEmits<{ changed: [value: ArchiveDeletion]; failure: [reason: unknown] }>()
const open = ref(false), opening = ref(false), sending = ref(false), error = ref(''), snapshot = ref<Archive>(), state = ref<ArchiveDeletion>()
const status = computed(() => state.value?.status || props.archive.deletionStatus)
const confirmed = computed(() => open.value && props.canDelete && !!snapshot.value?.deleteToken?.trim() && !sending.value && !['deleting', 'deleted'].includes(status.value || ''))
let alive = true, epoch = 0, timer: ReturnType<typeof setTimeout> | undefined
const valid = (current: number) => alive && current === epoch && props.canDelete
function fail(reason: unknown) {
  const code = reason instanceof IdentityError ? reason.status : 0
  error.value = code === 409 ? '成品内容已变化，请关闭后重新确认。' : code === 404 ? '成品不存在或已不可访问，请刷新列表。' : '删除未完成，请刷新状态后重试。原任务和原始资料保留。'
  if ([401, 403].includes(code)) { ++epoch; open.value = false; snapshot.value = undefined; clearTimeout(timer); emit('failure', reason); return true }
  return false
}
function schedule() { clearTimeout(timer); if (alive && props.canDelete && status.value === 'deleting') timer = setTimeout(() => { void poll() }, 2000) }
function apply(value: ArchiveDeletion) {
  state.value = value; error.value = value.status === 'delete_failed' ? '删除未完成，可重试删除。原任务和原始资料保留。' : ''
  open.value = false; snapshot.value = undefined; emit('changed', value); schedule()
}
async function poll() {
  const current = epoch
  try { const value = await props.api.deletion(props.archive.id); if (valid(current)) apply(value) }
  catch (reason) { if (valid(current) && !fail(reason)) schedule() }
}
async function openDialog() {
  if (!props.canDelete || opening.value || sending.value || ['deleting', 'deleted'].includes(status.value || '')) return
  const current = ++epoch; opening.value = true; error.value = ''; snapshot.value = undefined
  try {
    const value = await props.api.deletionPreview(props.archive.id)
    if (!valid(current)) return
    if (value.deletionStatus === 'deleting') { apply({ archiveId: value.id, status: 'deleting', error: null }); return }
    snapshot.value = value; state.value = undefined; open.value = true
    if (!value.deleteToken?.trim()) error.value = '成品确认信息已失效，请刷新页面后重试。'
  } catch (reason) { if (valid(current)) fail(reason) }
  finally { if (alive && current === epoch) opening.value = false }
}
async function remove() {
  if (!confirmed.value || !snapshot.value?.deleteToken) return
  const current = epoch, value = snapshot.value; sending.value = true; error.value = ''
  try { const result = await props.api.remove(value.id, value.deleteToken!); if (valid(current)) apply(result) }
  catch (reason) {
    if (!valid(current) || fail(reason)) return
    snapshot.value = undefined
    // 请求超时可能已受理，只读查询状态，绝不自动再次提交删除。
    if (!(reason instanceof IdentityError) || reason.status === 0 || reason.status >= 500) {
      try { const result = await props.api.deletion(value.id); if (valid(current)) apply(result) }
      catch (verification) { if (valid(current)) fail(verification) }
    }
  } finally { if (alive && current === epoch) sending.value = false }
}
watch(() => props.archive.deletionStatus, () => { if (!state.value) schedule() }, { immediate: true })
watch(() => props.canDelete, allowed => { ++epoch; clearTimeout(timer); open.value = false; snapshot.value = undefined; opening.value = false; sending.value = false; if (allowed) schedule() })
onUnmounted(() => { alive = false; ++epoch; clearTimeout(timer); snapshot.value = undefined })
</script>
<style scoped>
.archive-delete { border-top: 1px solid var(--el-border-color-lighter); margin-top: 12px; padding-top: 8px; }
.archive-delete p { overflow-wrap: anywhere; }
.archive-delete > p { color: var(--el-color-danger); font-size: 12px; margin: 6px 0; }
.archive-delete-name { overflow-wrap: anywhere; }
</style>
