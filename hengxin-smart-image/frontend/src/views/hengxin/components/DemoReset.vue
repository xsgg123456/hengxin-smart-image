<template><ElButton :loading="busy" @click="reset">重置当前 Demo 场景</ElButton></template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getService } from '@/api/hengxin/client'
const busy = ref(false)
async function reset() {
  if (import.meta.env.MODE !== 'demo') return
  try { await ElMessageBox.confirm('当前演示场景的上传、任务、模板和配置将恢复初始数据。其他场景不受影响。', '重置 Demo', { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' }) } catch { return }
  busy.value = true
  try {
    const { demoKey, writeDemo } = await import('@/api/hengxin/demo-storage')
    const { lockDemo } = await import('@/api/hengxin/demo-lock')
    // 初始化失败也可以恢复；再次取锁确保不删除另一标签页正在使用的数据。
    try { await (await getService()).dispose() } catch { /* 失败的初始化没有活动服务 */ }
    const release = await lockDemo(demoKey())
    try { await writeDemo(demoKey()) } finally { await release() }
    window.location.reload()
  } catch (reason) { ElMessage.error(reason instanceof Error ? reason.message : '重置失败，请刷新后重试') }
  finally { busy.value = false }
}
</script>
