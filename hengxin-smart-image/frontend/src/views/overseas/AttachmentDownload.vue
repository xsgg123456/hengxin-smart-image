<template>
  <div class="attachment-download">
    <ElButton :loading="busy" @click="download">下载原文件</ElButton>
    <ElButton v-if="busy" text @click="cancel">取消检查</ElButton>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="started" role="status">已发起下载，请在浏览器中查看进度。</p>
  </div>
</template>
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { downloadAttachment } from '@/api/overseas/attachment-download'
import { IdentityError } from '@/api/identity/request'
const props = defineProps<{ url: string; name: string }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const busy = ref(false), error = ref(''), started = ref(false)
let controller: AbortController | undefined
function cancel() { controller?.abort(); controller = undefined; busy.value = false; started.value = false; error.value = '' }
async function download() {
  if (busy.value) return
  const current = new AbortController(); controller = current; busy.value = true; error.value = ''; started.value = false
  try { await downloadAttachment(props.url, props.name, current.signal); if (controller === current) started.value = true }
  catch (reason) {
    if (controller === current) {
      error.value = reason instanceof Error ? reason.message : '下载失败，请重试'
      if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
    }
  }
  finally { if (controller === current) { controller = undefined; busy.value = false } }
}
watch(() => props.url, cancel)
onUnmounted(cancel)
</script>
<style scoped>
.attachment-download { min-width: 0; }
.attachment-download p { font-size: 12px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; margin: 6px 0; }
.attachment-download [role="alert"] { color: var(--el-color-danger); }
.attachment-download [role="status"] { color: var(--el-text-color-secondary); }
</style>
