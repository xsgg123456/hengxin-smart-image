<template>
  <aside class="session-list" aria-label="任务会话列表">
    <div class="session-list-title"><strong>会话 <small>{{ sessions.length }}/10</small></strong><ElButton text size="small" @click="$emit('close')">收起</ElButton></div>
    <ElButton class="session-create" type="primary" plain :disabled="!canCreate" @click="$emit('create')">＋ 新建会话</ElButton>
    <p v-if="sessions.length >= 10" class="session-limit">已达 10 个上限，删除会话后可新建。</p>
    <div class="session-items">
      <div v-for="s in sessions" :key="s.id" class="session-item" :class="{ active: s.id === activeId }">
        <button class="session-switch" :aria-pressed="s.id === activeId" @click="$emit('select', s)">
          <span class="session-name" :title="s.name">{{ s.name }}</span>
          <span class="session-status" :class="{ running: running(s), unread: s.unread }"><span v-if="running(s)" class="session-spinner" />{{ label(s) }}<small v-if="s.draft"> · 有草稿</small></span>
        </button>
        <ElDropdown trigger="click" @command="command => $emit('action', command, s)"><ElButton text size="small" :aria-label="`管理${s.name}`">⋯</ElButton><template #dropdown><ElDropdownMenu><ElDropdownItem command="rename" :disabled="disabled || !!s.deletionStatus">重命名</ElDropdownItem><ElDropdownItem command="delete" divided :disabled="disabled || running(s) || s.deletionStatus === 'deleting'">{{ s.deletionStatus === 'delete_failed' ? '重试删除' : '删除会话' }}{{ running(s) ? '（请先停止）' : '' }}</ElDropdownItem></ElDropdownMenu></template></ElDropdown>
      </div>
    </div>
    <p class="session-footnote">上下文与文件独立<br>成品归入当前工作流任务</p>
  </aside>
</template>
<script setup lang="ts">
import type { SessionView as Session } from './studio-session-state'
import { sessionLabel as label, sessionRunning as running } from './studio-session-state'
defineProps<{ sessions: Session[]; activeId: string; disabled: boolean; canCreate: boolean }>()
defineEmits<{ close: []; create: []; select: [s: Session]; action: [command: string, s: Session] }>()
</script>
