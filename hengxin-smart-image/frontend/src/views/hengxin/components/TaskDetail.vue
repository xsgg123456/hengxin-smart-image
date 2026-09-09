<template>
  <ElDrawer v-model="open" :title="task?.name || '任务详情'" size="82%" class="hx-detail" destroy-on-close>
    <template v-if="task">
      <div class="hx-detail-toolbar"><div><ElTag>{{ labels[task.mode] }}</ElTag><span class="hx-muted">{{ task.id }} · {{ task.time }}</span></div><div><ElButton :disabled="task.state !== '待查看'" @click="edit(-1)">整套修改</ElButton><ElButton :disabled="task.state !== '待查看'" @click="downloadSet(task.images, task.name)">{{ isMockMode ? '下载整套示例' : '下载整套' }}</ElButton><ElButton type="primary" :disabled="task.state !== '待查看' || task.archived" @click="archiveTask(task)">{{ task.archived ? '已归档' : '归档到成品库' }}</ElButton></div></div>
      <ElAlert v-if="isMockMode" title="交互演示：以下为示例图片，尚未调用真实 Skill。修改操作演示版本与状态变化。" type="info" show-icon :closable="false" />
      <div v-if="task.state !== '待查看'" class="hx-gap"><ElProgress v-if="task.progress !== null" :percentage="task.progress" :status="task.state === '失败' ? 'exception' : undefined" /><p>{{ task.state === '失败' ? '执行失败，已有图片保留，请查看错误记录后重试。' : (isMockMode ? '正在演示后台处理流程，请稍候…' : '后台处理中，请稍候…') }}</p><ElButton v-if="task.state === '失败'" type="primary" @click="retry">重试任务</ElButton></div>
      <div class="hx-result-grid"><ElCard v-for="(p, i) in task.images" :key="i" shadow="never" class="art-card"><ElImage :src="p.url" :alt="p.name" :preview-src-list="task.images.map(x => x.url)" :initial-index="i" fit="contain" preview-teleported /><div class="hx-result-meta"><strong>{{ p.name }}</strong><ElTag type="info" size="small">v{{ p.version || 1 }}</ElTag></div><div class="hx-row"><ElButton text type="primary" :disabled="task.state !== '待查看'" @click="edit(i)">修改这张</ElButton><ElButton text @click="downloadPicture(p)">{{ isMockMode ? '下载示例' : '下载图片' }}</ElButton></div></ElCard></div>
      <ElCollapse class="hx-gap"><ElCollapseItem :title="`修改记录（${task.feedback.length}）`"><ElEmpty v-if="!task.feedback.length" description="尚无修改意见" :image-size="60" /><p v-for="(text, i) in task.feedback" :key="i" class="hx-log">{{ text }}</p></ElCollapseItem></ElCollapse>
    </template>
  </ElDrawer>
  <ElDialog v-model="feedbackOpen" :title="target < 0 ? '整套修改意见' : `修改第 ${target + 1} 张图片`" width="520px" append-to-body>
    <p class="hx-muted">{{ target < 0 ? '本轮意见应用于整套图片。' : '仅重新生成这一张，其余图片保留。' }}</p><ElInput v-model="feedback" type="textarea" :rows="5" placeholder="描述需要调整的内容，例如：壁纸完整显示，保留手机边框和反光。" maxlength="1000" show-word-limit />
    <template #footer><ElButton @click="feedbackOpen = false">取消</ElButton><ElButton type="primary" :disabled="!feedback.trim()" :loading="submitting" @click="applyFeedback">提交修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { ref } from 'vue'
import { isMockMode } from '@/api/hengxin/client'
import { labels, run, archiveTask, type Task } from '../model'
import { downloadPicture, downloadSet } from '../download'
const open = defineModel<boolean>({ default: false })
const props = defineProps<{ task?: Task }>()
const feedbackOpen = ref(false), target = ref(-1), feedback = ref('')
function edit(index: number) { target.value = index; feedback.value = ''; feedbackOpen.value = true }
const submitting = ref(false)
async function retry() {
  if (!props.task || submitting.value) return
  submitting.value = true
  try { await run(props.task) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '重试失败') }
  finally { submitting.value = false }
}
async function applyFeedback() {
  if (!props.task || !feedback.value.trim() || submitting.value) return
  submitting.value = true
  try { await run(props.task, target.value, feedback.value.trim()); feedbackOpen.value = false }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '提交失败') }
  finally { submitting.value = false }
}
</script>
