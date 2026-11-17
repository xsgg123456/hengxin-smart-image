<template>
  <section class="hx-page wm-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">WORKSPACE SESSIONS</span><h1>工作台会话</h1><p>查看成员的对话内容与执行进度，跟进新品生成和产品替换。</p></div><ElTag effect="plain">超级管理员 · 只读查看</ElTag></div>
    <ElResult v-if="denied" icon="warning" title="仅超级管理员可查看" :sub-title="error" />
    <template v-else>
      <div class="wm-sync"><span :class="{ stale: !!error }"><i :class="['wm-dot', error ? 'failed' : 'running']" />{{ error ? '同步已中断，当前显示最后一次成功内容' : autoSync ? '自动同步' : '自动同步已暂停' }}<small>最后同步：{{ formatBeijingTime(lastSuccess, '尚未同步') }}（北京时间）</small></span><div><ElSwitch v-model="autoSync" aria-label="自动同步" /><ElButton :loading="loading" @click="refresh">刷新</ElButton></div></div>
      <ElAlert v-if="error" class="wm-sync-error" :title="error" type="error" :closable="false" />
      <template v-if="selectedId">
        <SessionDetail v-if="detail" :key="selectedId" :detail="detail" :transcript="transcript" @back="choose('')" @select="choose" @failure="failure" />
        <ElCard v-else shadow="never"><ElButton @click="choose('')">← 返回会话列表</ElButton><ElSkeleton v-if="loading" :rows="5" animated /><ElEmpty v-else description="会话内容不可用" /></ElCard>
      </template>
      <ElCard v-else class="art-card hx-section wm-list" shadow="never">
        <div class="wm-statuses"><ElButton v-for="key in statusOptions" :key="key" text :class="{ selected: filters.status === key }" @click="filters.status = key"><i v-if="key" :class="['wm-dot', key]" />{{ key ? labels[key] : '全部会话' }}<strong>{{ count(key) }}</strong></ElButton><span>按最近活动排序</span></div>
        <div class="wm-filters"><label>成员<ElSelect v-model="filters.ownerId" clearable filterable placeholder="全部成员" aria-label="筛选成员"><ElOption v-for="member in list?.members || []" :key="member.id" :label="member.name" :value="member.id" /></ElSelect></label><label>工作台<ElSelect v-model="filters.workspace" clearable placeholder="全部工作台" aria-label="筛选工作台"><ElOption v-for="workspace in domesticWorkspaces" :key="workspace.key" :label="workspace.title" :value="workspace.key" /></ElSelect></label><label class="wm-search">会话<ElInput v-model="filters.search" clearable placeholder="搜索会话名称" aria-label="搜索会话名称" maxlength="200" /></label><ElButton @click="reset">重置筛选</ElButton></div>
        <div class="wm-table-note">{{ selectedMember }} · {{ filters.workspace ? workspaceName(filters.workspace) : '全部工作台' }} · {{ filters.status ? labels[filters.status] : '全部状态' }}<span>共 {{ list?.total ?? '—' }} 个会话</span></div>
        <ElTable v-loading="loading" :data="list?.items || []" class="hx-admin-table" row-key="id" empty-text="暂无匹配的会话，请调整筛选条件" @row-dblclick="choose($event.id)">
          <ElTableColumn label="成员" width="140"><template #default="{ row }"><div class="wm-person"><span class="wm-avatar">{{ row.ownerName?.[0] || '?' }}</span>{{ row.ownerName || '姓名未记录' }}</div></template></ElTableColumn>
          <ElTableColumn label="会话名称" min-width="255"><template #default="{ row }"><button class="wm-name" @click="choose(row.id)">{{ row.name }}</button><small class="wm-subtext">{{ row.turnCount ? `${row.turnCount} 轮对话` : '尚未发送消息' }}</small></template></ElTableColumn>
          <ElTableColumn label="工作台" min-width="200"><template #default="{ row }">{{ workspaceName(row.workspace) }}</template></ElTableColumn>
          <ElTableColumn label="状态" width="110"><template #default="{ row }"><ElTag :type="tagType(row.status)" size="small" effect="light">{{ labels[row.status] || row.status }}</ElTag></template></ElTableColumn>
          <ElTableColumn label="最近活动（北京时间）" width="190"><template #default="{ row }">{{ formatBeijingTime(row.updatedAt) }}</template></ElTableColumn>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton text type="primary" @click="choose(row.id)">查看会话</ElButton></template></ElTableColumn>
        </ElTable>
        <div class="wm-pagination"><span>只读查看已提交的消息、附件与执行过程</span><ElPagination v-model:current-page="filters.page" :page-size="filters.pageSize" :total="list?.total || 0" layout="total, prev, pager, next" @current-change="refresh" /></div>
      </ElCard>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatBeijingTime } from '@/utils/beijing-time'
import type { SessionStatus } from '@/api/hengxin/workspace-sessions'
import SessionDetail from './SessionDetail.vue'
import { useMonitor } from './use-monitor'
import { domesticWorkspaces, labels, statusOptions, tagType, workspaceName } from './presentation'
import '@/views/shared/studio/studio.css'
import './style.css'
const route = useRoute(), router = useRouter()
const { filters, list, detail, transcript, selectedId, autoSync, loading, denied, error, lastSuccess, refresh, select, filterChanged, reset, failure } = useMonitor()
const count = (key: string) => list.value?.counters[(key || 'total') as SessionStatus | 'total'] ?? '—'
const selectedMember = computed(() => filters.ownerId ? list.value?.members.find(member => member.id === filters.ownerId)?.name || '已选成员' : '全部成员')
function choose(id: string) { void router.push({ query: { ...route.query, session: id || undefined } }) }
watch(() => route.query.session, id => select(typeof id === 'string' ? id : ''), { immediate: true })
watch(() => [filters.ownerId, filters.workspace, filters.status, filters.search], filterChanged)
watch(autoSync, enabled => { if (enabled) void refresh() })
</script>
