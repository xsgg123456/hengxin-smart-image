<template>
  <article class="domestic-chat-message" :class="message.role">
    <div class="domestic-message-name">{{ message.role === 'user' ? message.actorName?.trim() || '未知操作人' : 'Codex' }}<small v-if="message.role === 'assistant'">{{ message.status === 'stopped' ? '已停止' : '已回复' }}</small><time :datetime="message.createdAt" title="北京时间">{{ formatBeijingTime(message.createdAt, '时间未记录') }}</time></div>
    <div class="domestic-message-bubble"><p>{{ message.text }}</p><div v-if="message.files?.length" class="message-assets"><button v-for="asset in message.files" :key="asset.id" @click="$emit('preview', asset)"><img v-if="asset.image" :src="asset.url" :alt="asset.name"><ElIcon v-else><Document /></ElIcon><span>{{ asset.name }}</span></button></div></div>
  </article>
</template>
<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'
import { formatBeijingTime } from '@/utils/beijing-time'
import type { Asset, Message } from './state'
import './messages.css'
defineProps<{ message: Message }>()
defineEmits<{ preview: [asset: Asset] }>()
</script>
