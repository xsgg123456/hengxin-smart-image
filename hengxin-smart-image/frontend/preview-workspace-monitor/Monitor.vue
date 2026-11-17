<template>
  <section class="hx-page wm-page">
    <div class="wm-preview"><span>交互预览 · 示例人员与会话 · 未连接真实业务</span><div><span>预览状态</span><ElSelect v-model="scene" aria-label="预览状态" size="small"><ElOption label="正常查看" value="normal" /><ElOption label="同步中断" value="offline" /><ElOption label="暂无会话" value="empty" /><ElOption label="无权限" value="denied" /></ElSelect></div></div>
    <div class="hx-heading"><div><span class="hx-eyebrow">WORKSPACE SESSIONS</span><h1>工作台会话</h1><p>查看成员的对话内容与执行进度，跟进新品生成和产品替换。</p></div><ElTag effect="plain">超级管理员 · 只读查看</ElTag></div>
    <ElResult v-if="scene === 'denied'" icon="warning" title="仅超级管理员可查看" sub-title="当前演示身份没有查看他人会话的权限。"><template #extra><ElButton @click="scene = 'normal'">返回管理员预览</ElButton></template></ElResult>
    <template v-else>
      <div class="wm-sync"><span :class="{ stale: scene === 'offline' }"><i :class="['wm-dot', scene === 'offline' ? 'failed' : 'running']" />{{ scene === 'offline' ? '同步已中断，当前显示最后一次内容' : autoSync ? '自动同步' : '自动同步已暂停' }}<small>最后同步：{{ synchronizedAt }}</small></span><div><ElSwitch v-model="autoSync" aria-label="自动同步" :disabled="scene === 'offline'" /><ElButton :loading="refreshing" @click="refresh">刷新</ElButton></div></div>
      <SessionDetail v-if="selected && scene !== 'empty'" :key="selected.id" :session="selected" @back="close" @select="choose" />
      <ElCard v-else class="art-card hx-section wm-list" shadow="never">
        <div class="wm-statuses"><ElButton v-for="key in statusOptions" :key="key" text :class="{ selected: status === key }" @click="status = key"><i v-if="key !== 'all'" :class="['wm-dot', key]" />{{ key === 'all' ? '全部会话' : labels[key] }}<strong>{{ count(key) }}</strong></ElButton><span>按最近活动排序</span></div>
        <div class="wm-filters"><label>成员<ElSelect v-model="person" clearable placeholder="全部成员" aria-label="筛选成员"><ElOption v-for="name in people" :key="name" :label="name" :value="name" /></ElSelect></label><label>工作台<ElSelect v-model="workspace" clearable placeholder="全部工作台" aria-label="筛选工作台"><ElOption v-for="w in domesticWorkspaces" :key="w.key" :label="w.title" :value="w.key" /></ElSelect></label><label class="wm-search">会话<ElInput v-model="keyword" clearable placeholder="搜索会话名称" aria-label="搜索会话名称" /></label><ElButton @click="reset">重置筛选</ElButton></div>
        <div class="wm-table-note">{{ person || '全部成员' }} · {{ workspace ? workspaceName(workspace) : '全部工作台' }} · {{ status === 'all' ? '全部状态' : labels[status] }}<span>共 {{ filtered.length }} 个会话</span></div>
        <ElTable :data="pageRows" class="hx-admin-table" row-key="id" empty-text="暂无匹配的会话，请调整筛选条件" @row-dblclick="choose">
          <ElTableColumn label="成员" width="140"><template #default="{ row }"><div class="wm-person"><span class="wm-avatar">{{ row.person[0] }}</span>{{ row.person }}</div></template></ElTableColumn>
          <ElTableColumn label="会话名称" min-width="255"><template #default="{ row }"><button class="wm-name" @click="choose(row)">{{ row.name }}</button><small class="wm-subtext">{{ row.turns ? `${row.turns} 轮对话` : '尚未发送消息' }}</small></template></ElTableColumn>
          <ElTableColumn label="工作台" min-width="200"><template #default="{ row }">{{ workspaceName(row.workspace) }}</template></ElTableColumn>
          <ElTableColumn label="状态" width="110"><template #default="{ row }"><ElTag :type="tagType(row.status)" size="small" effect="light">{{ labels[row.status as State] }}</ElTag></template></ElTableColumn>
          <ElTableColumn label="最近活动" width="145"><template #default="{ row }">今天 {{ row.time }}</template></ElTableColumn>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton text type="primary" @click="choose(row)">查看会话</ElButton></template></ElTableColumn>
        </ElTable>
        <div class="wm-pagination"><span>只读查看已提交的消息、附件与执行过程</span><ElPagination v-model:current-page="page" :page-size="10" :total="filtered.length" layout="total, prev, pager, next" /></div>
      </ElCard>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SessionDetail from './SessionDetail.vue'
import { autoSync, domesticWorkspaces, labels, scene, sessions, sync, synchronizedAt, tagType, workspaceName, type Session, type State } from './data'
const route = useRoute(), router = useRouter()
const person = ref(''), workspace = ref(''), keyword = ref(''), status = ref<State | 'all'>('all'), page = ref(1), refreshing = ref(false)
const statusOptions: (State | 'all')[] = ['all', 'running', 'queued', 'succeeded', 'failed']
const people = [...new Set(sessions.value.map(s => s.person))]
const selected = computed(() => sessions.value.find(s => s.id === route.query.session))
const available = computed(() => scene.value === 'empty' ? [] : sessions.value)
const scoped = computed(() => available.value.filter(s => (!person.value || s.person === person.value) && (!workspace.value || s.workspace === workspace.value) && s.name.includes(keyword.value.trim())))
const count = (key: State | 'all') => scoped.value.filter(s => key === 'all' || s.status === key).length
const filtered = computed(() => scoped.value.filter(s => status.value === 'all' || s.status === status.value))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * 10, page.value * 10))
watch([person, workspace, keyword, status, scene], () => { page.value = 1 })
function choose(row: Session) { void router.push({ query: { session: row.id } }) }
function close() { void router.push({ query: {} }) }
function reset() { person.value = workspace.value = keyword.value = ''; status.value = 'all' }
let refreshTimer: ReturnType<typeof setTimeout> | undefined
function refresh() { refreshing.value = true; refreshTimer = setTimeout(() => { if (scene.value === 'offline') scene.value = 'normal'; sync(); refreshing.value = false }, 450) }
const timer = setInterval(() => { if (autoSync.value && document.visibilityState === 'visible') sync() }, 3000)
onUnmounted(() => { clearInterval(timer); clearTimeout(refreshTimer) })
</script>
