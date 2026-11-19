<template>
  <section class="hx-page tc-page">
    <ElResult v-if="denied" icon="warning" title="无权查看任务" :sub-title="error" />
    <template v-else>
      <div v-if="!taskId" class="hx-heading"><div><span class="hx-admin-kicker">{{ management ? 'TASK CENTER' : 'DESIGN TASKS' }}</span><h1>{{ workspace?.title || '任务中心' }}</h1><p>{{ management ? '按成员和业务查看全部任务，跟进各方案的对话与执行过程。' : '为这项业务创建任务，再在任务内探索不同设计方案。' }}</p></div><ElTag v-if="management" type="info">超级管理员 · 只读查看</ElTag><ElButton v-else type="primary" :icon="Plus" :disabled="busy || !!pending" @click="openCreate">新建任务</ElButton></div>
      <div v-if="management || managed" class="wm-sync"><span :class="{ stale: !!error }">{{ error ? '同步已中断，当前显示最后一次成功内容' : autoSync ? '自动同步' : '自动同步已暂停' }}<small>最后同步：{{ formatBeijingTime(lastSuccess, '尚未同步') }}（北京时间）</small></span><div><ElSwitch v-model="autoSync" aria-label="自动同步任务" /><ElButton :loading="loading" @click="refresh">刷新</ElButton></div></div>
      <ElAlert v-if="error || notice" :title="error || notice" :type="error ? 'error' : 'warning'" :closable="false"><ElButton v-if="error" text @click="refresh">重新加载</ElButton></ElAlert>
      <ElAlert v-if="pending && !managed" title="上次任务操作结果尚未确认，原请求已保留，请核实后继续。" type="warning" :closable="false"><ElButton :loading="busy" @click="retry">核实任务操作</ElButton></ElAlert>
      <TaskList v-if="!taskId" :filters="filters" :list="list" :workspace="workspace" :management="management" :actor="actor" :loading="loading" :busy="busy || !!pending" @reset="reset" @enter="enter" @action="taskAction" @create="openCreate" />
      <template v-else>
        <div class="tc-back"><ElButton :icon="ArrowLeft" @click="back">返回任务列表</ElButton><span>{{ taskWorkspace?.group }} / {{ taskWorkspace?.title }}</span><ElTag v-if="management || managed" type="info">{{ management ? '超级管理员 · 只读查看' : '只读查看' }}</ElTag></div>
        <template v-if="task && taskWorkspace">
          <div class="hx-heading tc-task-heading"><div><span class="hx-admin-kicker">DESIGN TASK</span><h1>{{ task.name }}</h1><p>创建人：{{ task.ownerName }} <span class="tc-separator">·</span> {{ task.conversationCount }} 个方案会话 <span class="tc-separator">·</span> 最近更新 {{ formatBeijingTime(task.updatedAt) }}</p></div><div class="tc-actions"><ElTag :type="task.completed ? 'success' : 'primary'">{{ task.completed ? '已完成' : '进行中' }}</ElTag><ElButton v-if="!management && task.ownerId === actor" :disabled="busy || !!pending || !!task.activeConversationCount || !!task.deletionStatus || (!task.completed && !taskReady)" @click="taskAction('complete', task)">{{ task.completed ? '重新打开任务' : '标记任务完成' }}</ElButton></div></div>
          <ElAlert v-if="task.deletionStatus" :title="task.deletionStatus === 'deleting' ? '正在清理任务会话及源文件，请等待实际清理完成。' : task.deletionError || '删除失败，请重试。'" type="warning" :closable="false"><ElButton v-if="task.deletionStatus === 'delete_failed' && !management && task.ownerId === actor" :disabled="busy" @click="taskAction('delete', task)">重试删除任务</ElButton></ElAlert>
          <ManagedTaskWorkspace v-if="managed" :business-view="!management" :key="`${actor}:${task.id}`" :detail="managed" :auto-sync="autoSync" :initial-session="typeof route.query.session === 'string' ? route.query.session : ''" @failure="failure" />
          <DomesticWorkspace v-else-if="!management && task.ownerId === actor && !task.deletionStatus" :key="`${actor}:${task.id}`" :config="taskWorkspace" :actor="actor" :task="task" @changed="refresh" @lifecycle-ready="taskReady = $event" />
        </template>
        <ElSkeleton v-else-if="loading" :rows="5" animated />
        <ElEmpty v-else description="任务不存在或当前身份无权查看" />
      </template>
    </template>
    <ElDialog v-model="creating" title="新建任务" width="min(520px,94vw)" :close-on-click-modal="false"><p class="tc-dialog-intro">先为本次设计命名，再在任务内创建不同方案的会话。</p><ElForm label-position="top" @submit.prevent="createTask"><ElFormItem label="所属业务" required><ElInput :model-value="workspace ? `${workspace.group} / ${workspace.title}` : ''" disabled /><small class="tc-sub">已根据当前菜单绑定业务。</small></ElFormItem><ElFormItem label="任务名称" required :error="formError"><ElInput v-model="newName" maxlength="60" show-word-limit placeholder="例如：iPhone 17 透明手机壳新品主图" aria-label="任务名称" :disabled="busy || !!pending" @input="formError = ''" @keydown.enter.prevent="createTask" /></ElFormItem><div class="tc-create-note"><ElIcon><ChatDotRound /></ElIcon><span>创建后进入任务工作台，可新建多个方案会话。</span></div></ElForm><template #footer><ElButton :disabled="busy" @click="creating = false">取消</ElButton><ElButton type="primary" :loading="busy" :disabled="!!pending" @click="createTask">创建并进入</ElButton></template></ElDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Plus, ArrowLeft, ChatDotRound } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/modules/user'
import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
import type { DomesticTask } from '@/api/hengxin/domestic-tasks'
import { formatBeijingTime } from '@/utils/beijing-time'
import DomesticWorkspace from './DomesticWorkspace.vue'
import TaskList from './TaskList.vue'
import ManagedTaskWorkspace from '../admin/workspace-sessions/ManagedTaskWorkspace.vue'
import { createWorkspaceSessionsApi } from '@/api/hengxin/workspace-sessions'
import { useTasks } from './use-tasks'
import './tasks.css'
import '../admin/workspace-sessions/style.css'
const route = useRoute(), router = useRouter(), user = useUserStore()
const management = computed(() => route.path === '/management/task-center')
const workspace = computed(() => domesticWorkspaces.find(item => item.path === route.path))
const actor = computed(() => String(user.getUserInfo.userId || ''))
const taskId = computed(() => typeof route.query.task === 'string' ? route.query.task : '')
function enter(value: DomesticTask) { creating.value = false; void router.push({ path: management.value ? '/management/task-center' : workspace.value!.path, query: { ...route.query, task: value.id, session: undefined } }) }
function back() { void router.push({ path: route.path, query: { ...route.query, task: undefined, session: undefined } }) }
const { filters, list, task, managed, loading, busy, error, notice, denied, pending, autoSync, lastSuccess, refresh, reset, failure, create, update, remove, retry } = useTasks(() => ({ actor: actor.value, workspace: workspace.value?.key || '', management: management.value, id: taskId.value }), enter, back)
const taskWorkspace = computed(() => domesticWorkspaces.find(item => item.key === task.value?.workspace))
const taskReady = ref(false)
const creating = ref(false), newName = ref(''), formError = ref('')
function openCreate() { if (management.value || !workspace.value || pending.value) return; newName.value = ''; formError.value = ''; creating.value = true }
async function createTask() { if (!newName.value.trim() || newName.value.trim().length > 60) { formError.value = '请输入1至60个字符'; return }; if (await create(newName.value.trim())) creating.value = false }
async function taskAction(command: string, value: DomesticTask) {
  if (management.value || value.ownerId !== actor.value || busy.value || pending.value) return
  try {
    if (command === 'rename' && !value.completed && !value.deletionStatus) {
      const answer = await ElMessageBox.prompt('使用清晰的名称，方便区分不同任务。', '重命名任务', { inputValue: value.name, inputValidator: name => !!name?.trim() && name.trim().length <= 60 || '请输入1至60个字符', confirmButtonText: '保存', cancelButtonText: '取消' })
      await update(value, { name: answer.value.trim() })
    } else if (command === 'complete' && !value.activeConversationCount && !value.deletionStatus) {
      await ElMessageBox.confirm(value.completed ? '重新打开后可以继续设计。' : '完成后保留阅读和下载，需要继续设计时可重新打开。', value.completed ? '重新打开任务' : '标记任务完成', { confirmButtonText: '确定', cancelButtonText: '取消' })
      await update(value, { completed: !value.completed })
    } else if (command === 'delete' && !value.activeConversationCount && value.deletionStatus !== 'deleting') {
      await ElMessageBox.confirm(`删除「${value.name}」及全部方案会话和源文件？已归档成品保留。`, '删除任务', { type: 'warning', confirmButtonText: value.deletionStatus === 'delete_failed' ? '重试删除' : '确认删除', cancelButtonText: '取消' })
      await remove(value)
    }
  } catch { /* User cancelled the confirmation. */ }
}
let legacyEpoch = 0
watch(() => [route.path, route.query.session, taskId.value], async () => {
  const token = ++legacyEpoch, id = route.query.session
  taskReady.value = false
  if (!management.value || taskId.value || typeof id !== 'string') return
  try {
    const value = await createWorkspaceSessionsApi().detail(id)
    if (token === legacyEpoch && value.session.taskId) await router.replace({ path: '/management/task-center', query: { task: value.session.taskId, session: id } })
  } catch (reason) { if (token === legacyEpoch) failure(reason) }
}, { immediate: true })
onScopeDispose(() => { ++legacyEpoch })
watch(() => route.path, () => { creating.value = false; reset() })
</script>
