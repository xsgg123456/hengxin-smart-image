<template>
  <section class="domestic-session-panel" aria-label="工作台会话列表">
    <header><strong>会话 <small>{{ sessions.length }}/10</small></strong><ElButton text size="small" aria-label="收起会话列表" @click="$emit('close')">收起</ElButton></header>
    <ElButton class="domestic-session-create" type="primary" plain :icon="Plus" :disabled="sessions.length >= 10" @click="$emit('create')">新建会话</ElButton>
    <p v-if="sessions.length >= 10" class="domestic-session-limit">已达 10 个上限，删除后可新建。</p>
    <div class="domestic-session-items">
      <div v-for="session in sessions" :key="session.id" class="domestic-session-item" :class="{ active: session.id === activeId }">
        <button class="domestic-session-switch" :aria-label="`切换到${session.name}`" :aria-pressed="session.id === activeId" @click="$emit('select', session)"><strong :title="session.name">{{ session.name }}</strong><span :class="{ running: session.running }"><i v-if="session.running"></i>{{ session.running ? '正在回复' : session.messages.length ? '可继续对话' : '未开始' }}<small v-if="session.draft || session.pending.length"> · 有草稿</small></span></button>
        <ElDropdown trigger="click" @command="command => $emit('action', command, session)"><ElButton text size="small" :aria-label="`管理${session.name}`">⋯</ElButton><template #dropdown><ElDropdownMenu><ElDropdownItem command="rename">重命名</ElDropdownItem><ElDropdownItem command="delete" divided :disabled="session.running">{{ session.running ? '删除会话（请先停止）' : '删除会话' }}</ElDropdownItem></ElDropdownMenu></template></ElDropdown>
      </div>
    </div>
    <footer>每个会话的对话、附件和草稿独立<br>切换会话不中断正在进行的回复</footer>
  </section>
</template>
<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import type { Conversation } from './state'
defineProps<{ sessions: Conversation[]; activeId: number }>()
defineEmits<{ close: []; create: []; select: [session: Conversation]; action: [command: string, session: Conversation] }>()
</script>
