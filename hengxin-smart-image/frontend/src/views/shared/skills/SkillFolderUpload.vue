<template>
  <ElDialog :model-value="open" title="上传 Skill 文件夹" width="min(760px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @close="close">
    <p>{{ domestic ? '一次拖入一个完整文件夹，包含根目录 SKILL.md。新增默认关闭且未绑定工作台；更新保留绑定和开关。' : '一次拖入一个完整文件夹，包含根目录 SKILL.md。新增默认关闭且未分配平台；更新保留平台和开关。' }}</p>
    <div class="folder-drop" :class="{ 'domestic-folder-drop': domestic }" :aria-busy="busy" @dragover.prevent @drop.prevent="drop">{{ scanning ? `正在完整扫描 · ${scanned} 项` : '将完整 Skill 文件夹拖到这里（包含空目录）' }}</div>
    <p class="hx-muted">单文件 64 MiB，整包 256 MiB，最多 1000 个文件、2000 个目录及文件条目。不支持目录读取的浏览器无法上传。</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="folder || transfer">
      <p><strong>{{ transfer?.package?.displayName || folder?.displayName || transfer?.rootName }}</strong> · {{ transfer?.package?.name || folder?.name }}</p>
      <p class="folder-description">{{ transfer?.package?.description || folder?.description }}</p>
      <p>{{ fileCount }} 个文件 · {{ directoryCount }} 个目录 · {{ sizeLabel }} · {{ statusText }}</p>
      <ElProgress v-if="transfer" :percentage="percentage" :status="transfer.status === 'failed' ? 'exception' : transfer.status === 'installed' ? 'success' : undefined" />
      <div class="folder-tree"><ElTree :data="tree" node-key="path" :default-expanded-keys="['']" /></div>
      <ElAlert v-if="transfer?.change === 'identical'" title="同名同内容已安装，无需重复安装" type="success" :closable="false" />
      <template v-if="transfer?.change === 'update' && transfer.diff">
        <ElAlert :title="domestic ? '同名 Skill 内容不同，请核对全部差异后确认更新。' : '同名 Skill 内容不同。请核对全部差异后明确确认更新；历史冻结版本保留。'" type="warning" :closable="false" />
        <div class="folder-diff"><div v-for="section in diffSections" :key="section.label"><strong>{{ section.label }}（{{ section.paths.length }}）</strong><p v-for="path in section.paths" :key="path">{{ path }}</p></div></div>
      </template>
      <p>完整性检查不代表已验证外部依赖或 Skill 实际运行效果。</p>
    </template>
    <details class="transfer-history" @toggle="historyToggle"><summary>查看服务器保存的上传状态</summary><ElButton :disabled="busy" @click="loadHistory">刷新上传状态</ElButton><p v-if="historyError">{{ historyError }}</p><p v-if="historyLoaded && !history.length">暂无上传记录</p><div v-for="item in history" :key="item.id" class="transfer-row"><span>{{ item.rootName }} · {{ stateLabel(item.status) }}</span><ElButton size="small" :disabled="busy" @click="resume(item)">查看 / 恢复</ElButton></div></details>
    <template #footer>
      <ElButton :disabled="busy" @click="close">关闭</ElButton>
      <ElButton v-if="transfer" :disabled="busy" @click="queryStatus">查询当前状态</ElButton>
      <ElButton v-if="transfer && canValidate" :disabled="busy" @click="revalidate">重新校验差异</ElButton>
      <ElButton v-if="transfer && !['installed', 'cancelled'].includes(transfer.status)" :disabled="busy" @click="cancelTransfer">取消当前上传</ElButton>
      <ElButton v-if="canUpload" type="primary" :loading="busy" @click="upload">{{ transfer ? '核验并重试上传' : '上传并安装' }}</ElButton>
      <ElButton v-if="transfer?.status === 'validated' && transfer.change !== 'identical'" type="primary" :loading="busy" @click="install">{{ transfer.change === 'update' ? '确认更新同名 Skill' : '安装 Skill（默认关闭）' }}</ElButton>
    </template>
  </ElDialog>
</template>
<script setup lang="ts">
import { randomUUID } from '../../../utils/browser-crypto'
import { computed, ref } from 'vue'
import { isDirectory, skillTransferError, type SkillTransfer, type SkillTransferApi } from '@/api/shared/skill-transfers'
import { droppedRoot, folderTree, scanFolder, type ScannedFolder } from './skill-folder-read'
const props = defineProps<{ open: boolean; api: SkillTransferApi; domestic?: boolean }>()
const emit = defineEmits<{ close: []; installed: []; failure: [reason: unknown] }>()
const busy = ref(false), scanning = ref(false), scanned = ref(0), error = ref(''), folder = ref<ScannedFolder>(), transfer = ref<SkillTransfer>()
const history = ref<SkillTransfer[]>([]), historyError = ref(''), historyLoaded = ref(false)
let requestKey = ''
const manifest = computed(() => transfer.value || folder.value)
const entries = computed(() => Object.entries(manifest.value?.entries || {}))
const fileCount = computed(() => entries.value.filter(([, e]) => !isDirectory(e)).length)
const directoryCount = computed(() => entries.value.length - fileCount.value)
const sizeLabel = computed(() => (entries.value.reduce((sum, [, e]) => sum + (isDirectory(e) ? 0 : e.size), 0) / 1024 / 1024).toFixed(2) + ' MiB')
const tree = computed(() => manifest.value ? folderTree(manifest.value) : [])
const percentage = computed(() => fileCount.value ? Math.min(100, Math.floor((transfer.value?.received.length || 0) / fileCount.value * 100)) : 0)
const stateLabel = (status: SkillTransfer['status']) => ({ uploading: '上传中 / 待续传', validated: '校验通过，待确认安装', installed: '已安装', failed: '失败，可查询并重试', cancelled: '已取消' }[status])
const statusText = computed(() => transfer.value ? stateLabel(transfer.value.status) : '已完整读取，尚未上传')
const canUpload = computed(() => !!folder.value && (!transfer.value || ['uploading', 'failed'].includes(transfer.value.status)))
const canValidate = computed(() => !!transfer.value && !['installed', 'cancelled'].includes(transfer.value.status) && entries.value.every(([path, entry]) => isDirectory(entry) || transfer.value!.received.includes(path)))
const diffSections = computed(() => [{ label: '新增', paths: transfer.value?.diff?.added || [] }, { label: '修改', paths: transfer.value?.diff?.modified || [] }, { label: '删除', paths: transfer.value?.diff?.removed || [] }])
function close() { if (!busy.value) emit('close') }
function failed(reason: unknown) { error.value = skillTransferError(reason); emit('failure', reason) }
function matches(scanned: ScannedFolder, saved: SkillTransfer) {
  const normalize = (entries: ScannedFolder['entries']) => JSON.stringify(Object.entries(entries).map(([path, entry]) => [path, isDirectory(entry) ? 'directory' : `${entry.size}:${entry.sha256}`]).sort(([a], [b]) => a.localeCompare(b)))
  return scanned.rootName === saved.rootName && normalize(scanned.entries) === normalize(saved.entries)
}
async function drop(event: DragEvent) {
  if (busy.value || !event.dataTransfer) return
  busy.value = true; scanning.value = true; scanned.value = 0; error.value = ''
  try {
    // DataTransfer entries must be captured synchronously inside the drop event.
    const root = droppedRoot(event.dataTransfer), result = await scanFolder(root, count => { scanned.value = count })
    if (transfer.value && ['uploading', 'failed'].includes(transfer.value.status) && !matches(result, transfer.value)) throw new Error('重新拖入的文件夹与待续传清单不同。请先完成当前上传，或关闭后选择另一条记录；不会混合文件')
    if (!transfer.value || ['installed', 'cancelled', 'validated'].includes(transfer.value.status)) { transfer.value = undefined; requestKey = randomUUID() }
    folder.value = result
  } catch (reason) { folder.value = undefined; failed(reason) }
  finally { busy.value = false; scanning.value = false }
}
async function upload() {
  if (busy.value || !folder.value) return
  busy.value = true; error.value = ''
  try {
    transfer.value = transfer.value ? await props.api.get(transfer.value.id) : await props.api.create({ rootName: folder.value.rootName, entries: folder.value.entries }, requestKey)
    if (transfer.value.status === 'installed') { emit('installed'); return }
    for (const [path, file] of Array.from(folder.value.files)) if (!transfer.value.received.includes(path)) transfer.value = await props.api.upload(transfer.value.id, path, file)
    transfer.value = await props.api.validate(transfer.value.id)
    if (transfer.value.error) error.value = transfer.value.error
    else if (transfer.value.status === 'validated' && transfer.value.change !== 'update') {
      transfer.value = await props.api.install(transfer.value.id, transfer.value.baseRelease ?? null)
      if (transfer.value.status === 'installed') emit('installed')
      else error.value = transfer.value.error || '安装尚未确认完成，请查询状态'
    }
  } catch (reason) { failed(reason) }
  finally { busy.value = false }
}
async function revalidate() {
  if (busy.value || !transfer.value || !canValidate.value) return
  busy.value = true; error.value = ''
  try { transfer.value = await props.api.validate(transfer.value.id); error.value = transfer.value.error || '' }
  catch (reason) { failed(reason) } finally { busy.value = false }
}
async function cancelTransfer() {
  if (busy.value || !transfer.value) return
  busy.value = true; error.value = ''
  try { await props.api.cancel(transfer.value.id); transfer.value = undefined; folder.value = undefined; requestKey = '' }
  catch (reason) { failed(reason) } finally { busy.value = false }
}
async function install() {
  if (busy.value || transfer.value?.status !== 'validated') return
  busy.value = true; error.value = ''
  try {
    transfer.value = await props.api.install(transfer.value.id, transfer.value.baseRelease ?? null)
    if (transfer.value.status === 'installed') emit('installed')
    else error.value = transfer.value.error || '安装尚未确认完成，请查询状态'
  } catch (reason) { failed(reason) }
  finally { busy.value = false }
}
async function queryStatus() {
  if (busy.value || !transfer.value) return
  busy.value = true; error.value = ''
  try { transfer.value = await props.api.get(transfer.value.id); error.value = transfer.value.error || ''; if (transfer.value.status === 'installed') emit('installed') }
  catch (reason) { failed(reason) } finally { busy.value = false }
}
async function loadHistory() {
  historyError.value = ''
  try { history.value = (await props.api.list()).items; historyLoaded.value = true }
  catch (reason) { historyError.value = skillTransferError(reason); emit('failure', reason) }
}
function historyToggle(event: Event) { if ((event.target as HTMLDetailsElement).open && !historyLoaded.value) void loadHistory() }
async function resume(item: SkillTransfer) {
  if (busy.value) return
  transfer.value = item; folder.value = undefined; requestKey = ''; await queryStatus()
  if (transfer.value && ['uploading', 'failed'].includes(transfer.value.status) && !error.value) error.value = '请重新拖入原文件夹，清单一致后可核验并继续上传'
}
</script>
<style scoped>
.folder-drop { border:1px dashed var(--el-color-primary); border-radius:8px; padding:24px 12px; margin:16px 0; text-align:center; }
.domestic-folder-drop { padding:30px 16px; border-color:var(--el-border-color); color:var(--art-gray-600); font-size:13px; line-height:1.5; }
.folder-tree,.folder-diff { max-height:280px; overflow:auto; margin:12px 0; }
.folder-description,.folder-diff p,.transfer-row { white-space:pre-wrap; overflow-wrap:anywhere; }
.folder-diff p { margin:4px 0; font-size:12px; }
.transfer-history { margin:16px 0; }
.transfer-row { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; padding:8px 0; }
:deep(.el-dialog__footer) { display:flex; justify-content:flex-end; flex-wrap:wrap; gap:8px; }
:deep(.el-dialog__footer .el-button) { margin-left:0; }
:deep(.el-tree-node__label) { white-space:normal; overflow-wrap:anywhere; }
:deep(.el-tree-node__content) { height:auto; min-height:26px; }
</style>
