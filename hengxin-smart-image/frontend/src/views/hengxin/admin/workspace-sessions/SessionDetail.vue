<template>
  <div class="wm-detail" :class="{ expanded }">
    <div class="wm-detail-heading"><ElButton v-if="!taskContext" @click="$emit('back')">← 返回会话列表</ElButton><span>{{ detail.session.ownerName }} / {{ workspaceName(detail.session.workspace) }}</span><div class="wm-detail-actions"><ElButton @click="materialsOpen = true">附件与结果</ElButton><ElButton :icon="FullScreen" :aria-pressed="expanded" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开' }}</ElButton></div></div>
    <div class="wm-workbench">
      <aside class="wm-conversations"><div class="wm-sidebar-title"><strong>{{ detail.session.ownerName }}</strong><span>{{ detail.siblingSessions.length }} 个会话</span></div><p>{{ taskContext ? '当前任务的方案会话' : '该成员的工作台会话' }}</p>
        <div class="wm-conversation-list"><button v-for="item in detail.siblingSessions" :key="item.id" :class="['wm-conversation', { active: item.id === detail.session.id }]" @click="$emit('select', item.id)"><span>{{ item.name }}</span><small>{{ workspaceName(item.workspace) }}</small><div><i :class="['wm-dot', item.status]" />{{ labels[item.status] }}<time>{{ formatBeijingTime(item.updatedAt).slice(5, 16) }}</time></div></button></div>
        <div class="wm-sidebar-note">以管理员身份只读查看<br>用户的会话继续独立执行</div>
      </aside>
      <main class="wm-chat"><header class="wm-chat-heading"><div><strong>{{ detail.session.name }}</strong><span>{{ workspaceName(detail.session.workspace) }} · {{ detail.session.turnCount }} 轮对话</span></div><ElTag :type="tagType(detail.session.status)">{{ labels[detail.session.status] }}</ElTag></header>
        <SessionMessages :turns="detail.workspace.turns" :transcript="transcript" :owner-name="detail.session.ownerName" @failure="$emit('failure', $event)" />
        <footer class="wm-readonly"><span>◇ 管理员只读查看 · 无法代发消息或修改用户内容</span></footer>
      </main>
    </div>
    <ElDrawer v-model="materialsOpen" title="附件与结果" size="min(460px, 94vw)" append-to-body destroy-on-close :z-index="4000"><p class="wm-muted">{{ detail.session.ownerName }} · {{ detail.session.name }}</p><ElTabs v-model="assetTab"><ElTabPane label="用户附件" name="inputs"><div class="studio-image-attachments"><ManagedAsset v-for="asset in inputs" :key="asset.id" :asset="asset" :group="inputs" title="用户附件" @failure="$emit('failure', $event)" /></div><ElEmpty v-if="!inputs.length" description="还没有已提交的附件" /></ElTabPane><ElTabPane label="生成结果" name="results"><div class="studio-pictures"><ManagedAsset v-for="asset in outputs" :key="asset.id" :asset="asset" :group="outputs" title="生成结果" result @failure="$emit('failure', $event)" /></div><ElEmpty v-if="!outputs.length" description="暂无已保存结果" /></ElTabPane></ElTabs></ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { FullScreen } from '@element-plus/icons-vue'
import type { SessionDetail } from '@/api/hengxin/workspace-sessions'
import type { StudioTranscript } from '@/api/shared/studio'
import { formatBeijingTime } from '@/utils/beijing-time'
import SessionMessages from './SessionMessages.vue'
import ManagedAsset from './ManagedAsset.vue'
import { labels, tagType, workspaceName } from './presentation'
const props = defineProps<{ detail: SessionDetail; transcript: StudioTranscript[]; taskContext?: boolean }>()
defineEmits<{ back: []; select: [id: string]; failure: [reason: unknown] }>()
const expanded = defineModel<boolean>('expanded', { default: false })
const materialsOpen = ref(false), assetTab = ref('inputs')
const inputs = computed(() => [...new Map(props.detail.workspace.turns.flatMap(turn => [...turn.attachments, ...turn.referencePictures]).map(asset => [asset.id, asset])).values()])
const outputs = computed(() => [...new Map(props.detail.workspace.turns.flatMap(turn => [...turn.pictures, ...(turn.outputs || [])]).map(asset => [asset.id, asset])).values()])
</script>
