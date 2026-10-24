<template>
  <ElDialog :model-value="true" title="取回文件" width="min(680px,94vw)" append-to-body @close="$emit('close')">
    <div class="recovery-body">
    <p>选择本会话仍存在的文件，保存后会显示在聊天记录中。最多选择 100 个，单个最大 500 MB。</p>
    <ElAlert v-if="readonly" title="当前会话只读。任务已完成时，请先解冻工作台再取回文件。" type="info" :closable="false" />
    <ElAlert v-else-if="busy || serverBusy" title="当前会话正在处理文件，请等待结束后刷新列表再取回。已保存的文件可继续使用。" type="info" :closable="false" />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <ElAlert v-if="result" :title="`已保存 ${result.saved.length} 个文件，${result.errors.length} 个未保存。`" :type="result.errors.length ? 'warning' : 'success'" :closable="false" />
    <ul v-if="result?.errors.length" class="recovery-errors" role="alert"><li v-for="item in result.errors" :key="item.id">{{ item.name }}：{{ item.message }}</li></ul>
    <p v-if="loading" role="status">正在查找本会话文件…</p>
    <p v-else-if="loaded && !items.length">没有可取回的文件。未生成、已删除或已覆盖且没有副本的文件无法恢复。</p>
    <div v-if="items.length" class="recovery-files" aria-label="可取回文件">
      <div v-for="file in items" :key="file.id" class="recovery-file">
        <ElCheckbox :model-value="selected.includes(file.id)" :disabled="blocked || (!selected.includes(file.id) && selected.length >= 100)" :aria-label="`选择 ${file.name}`" @change="value => toggle(file.id, !!value)">{{ file.name }}</ElCheckbox>
        <small>{{ sources[file.source] }} · {{ formatAttachmentSize(file.sizeBytes) }}</small><small>{{ file.path }}</small>
      </div>
    </div>
    </div>
    <template #footer><div class="recovery-footer"><span>已选 {{ selected.length }}/100</span><ElButton :disabled="saving" :loading="loading" @click="load">刷新列表</ElButton><ElButton @click="$emit('close')">关闭</ElButton><ElButton type="primary" :disabled="!canSave" :loading="saving" @click="recover">{{ result?.errors.length ? '重试所选文件' : '取回所选文件' }}</ElButton></div></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import { useStudioRecovery } from './use-studio-recovery'
const props = defineProps<{ taskId: string; conversationId: string; readonly: boolean; busy: boolean }>()
const emit = defineEmits<{ close: []; saved: []; failure: [reason: unknown] }>()
const { items, selected, loading, saving, serverBusy, error, result, loaded, blocked, canSave, load, recover, toggle } = useStudioRecovery(() => props, () => emit('saved'), reason => emit('failure', reason))
const sources = { work: '工作文件', native: '生成图片', snapshot: '本轮副本' }
</script>
<style scoped>
.recovery-body { max-height: 60dvh; overflow: auto; }
.recovery-files { max-height: 45vh; overflow: auto; margin: 12px 0; }
.recovery-file { border-bottom: 1px solid var(--el-border-color); padding: 8px 0; min-width: 0; }
.recovery-file small { display: block; color: var(--el-text-color-secondary); overflow-wrap: anywhere; }
.recovery-file :deep(.el-checkbox) { height: auto; max-width: 100%; align-items: flex-start; }
.recovery-file :deep(.el-checkbox__label) { white-space: normal; overflow-wrap: anywhere; min-width: 0; }
.recovery-errors { padding-left: 20px; overflow-wrap: anywhere; max-height: 20vh; overflow: auto; }
.recovery-footer { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; align-items: center; }
.recovery-footer .el-button + .el-button { margin-left: 0; }
</style>
