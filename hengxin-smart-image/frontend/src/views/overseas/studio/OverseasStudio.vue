<template>
  <section ref="workspace" class="studio-page" :style="{ '--studio-height': workspaceHeight }">
    <div class="studio-steps"><span class="done">① 运营提交图需</span><i></i><span class="done">② 设计人工审核</span><i></i><span class="active">③ AI 设计工作台</span><i></i><span>④ 归档成品库</span></div>
    <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }" @keydown.esc="expanded = false">
      <div class="studio-chat-heading"><strong>与 Codex 协作{{ data?.completed ? ' · 已完成' : '' }}</strong><div class="studio-actions"><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ data?.materials.length || 0 }}</ElButton><ElButton size="small" :loading="loading" @click="refresh">刷新</ElButton><ElButton size="small" :disabled="!canNewConversation" @click="conversationOpen = true">开始新对话</ElButton><ElButton size="small" type="primary" :disabled="locked || !selected.length" @click="archiveOpen = true">归档成品（{{ selected.length }}）</ElButton><ElButton size="small" :disabled="locked || !!data?.activeTurnId || !hasArchive" @click="completeOpen = true">完成任务</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton></div></div>
      <ElAlert v-if="error || limitError" :title="limitError || error" type="error" :closable="false" />
      <ElAlert v-if="pending" title="上次操作的结果尚未确认。请使用相同请求重试，避免重复生成或归档。" type="warning" :closable="false"><ElButton :loading="busy" :disabled="!task.capabilities.includes('task.design')" @click="retry">核实并重试上次操作</ElButton></ElAlert>
      <div class="studio-workspace"><section class="studio-conversation">
        <StudioTurns :turns="data?.turns || []" :transcript="transcript" :conversation-id="data?.conversationId" :selected="selected" :disabled="locked" @failure="fail" @group="toggleGroup" @toggle="toggle" @modify="modify" />
        <div class="studio-composer" @dragover.prevent @drop.prevent="drop" @paste="paste">
          <button class="studio-dropzone" :disabled="locked" :class="{ 'is-dragging': dragging }" @dragover.prevent.stop="dragging = true" @dragleave="dragging = false" @click="input?.click()">{{ uploading ? '正在上传…' : dragging ? '松开即可添加附件' : '拖拽图片或文件到这里，或点击上传' }} <small>最多 100 个附件 · 单个最大 500 MB</small></button>
          <div class="studio-attachments pending"><div v-for="asset in attachments" :key="asset.id" class="studio-attachment"><span :title="asset.name">{{ asset.name }} · {{ formatAttachmentSize(asset.sizeBytes) }}</span><AttachmentDownload :url="asset.url" :name="asset.name" @failure="fail" /><ElButton text :disabled="locked" :aria-label="`移除 ${asset.name}`" @click="attachments = attachments.filter(a => a.id !== asset.id)">×</ElButton></div><div v-for="picture in references" :key="picture.id" class="studio-attachment"><ElImage :src="picture.url" :preview-src-list="[picture.url]" preview-teleported /><span>修改 {{ picture.name }}</span><ElButton text :disabled="locked" @click="references = references.filter(p => p.id !== picture.id)">取消引用</ElButton></div></div>
          <ElInput v-model="text" type="textarea" :rows="2" resize="none" :disabled="locked" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown.ctrl.enter.prevent="send" />
          <div class="studio-compose-tools"><div class="studio-input-tools"><StudioSkillSelect v-model="skill" :skills="data?.skills || []" :disabled="locked" /></div><ElButton v-if="data?.activeTurnId" :loading="busy" :disabled="!editable || activeTurn?.status === 'cancelling'" @click="stop">停止</ElButton><ElButton v-else type="primary" :loading="busy" :disabled="!canSend" @click="send">发送</ElButton></div>
          <p class="studio-compose-note">支持 JPG/PNG/WebP、PDF/DOCX/PPTX/XLS/XLSX/CSV/TXT · Ctrl + Enter 发送。执行期间可离开，回来后继续。</p>
          <input ref="input" hidden type="file" multiple accept=".jpg,.jpeg,.png,.webp,.pdf,.docx,.pptx,.xls,.xlsx,.csv,.txt" @change="upload">
        </div>
      </section><StudioMaterials v-if="materialsOpen" :assets="data?.materials || []" :disabled="locked" @close="materialsOpen = false" @add="add" @failure="fail" /></div>
    </ElCard>
    <ElDialog v-model="conversationOpen" title="开始新对话" width="min(480px,94vw)" append-to-body><p>开始后将使用新的对话上下文。旧对话、任务材料和已生成或归档的成品都会保留。</p><p>草稿和当前引用将清空；需要使用旧材料时，请重新选择引用。</p><template #footer><ElButton @click="conversationOpen = false">取消</ElButton><ElButton type="primary" :loading="busy" :disabled="!canNewConversation" @click="doNewConversation">确认开始新对话</ElButton></template></ElDialog>
    <ElDialog v-model="archiveOpen" title="归档所选图片" width="min(600px,94vw)" append-to-body><p>将所选 {{ selected.length }} 张图片归入指定 SKU；归档后仍可继续对话。</p><ElSelect v-model="sku" aria-label="归档所属 SKU" placeholder="选择所属 SKU"><ElOption v-for="item in task.skus" :key="item.code" :value="item.code" :label="item.code" /></ElSelect><template #footer><ElButton @click="archiveOpen = false">取消</ElButton><ElButton type="primary" :disabled="locked || !sku || !selected.length" :loading="busy" @click="doArchive">确认归档</ElButton></template></ElDialog>
    <ElDialog v-model="completeOpen" title="确认完成任务" width="min(480px,94vw)" append-to-body><p>完成后不再接收新的设计意见。已归档成品将保留。</p><template #footer><ElButton @click="completeOpen = false">继续设计</ElButton><ElButton type="primary" :loading="busy" :disabled="locked || !!data?.activeTurnId" @click="doComplete">确认完成</ElButton></template></ElDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { TaskDetail } from '@/api/overseas/tasks'
import StudioTurns from './StudioTurns.vue'
import AttachmentDownload from '../AttachmentDownload.vue'
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import StudioMaterials from './StudioMaterials.vue'
import StudioSkillSelect from './StudioSkillSelect.vue'
import { useStudio } from './use-studio'
import './studio.css'
const props = defineProps<{ actorId: string; task: TaskDetail }>()
const emit = defineEmits<{ failure: [reason: unknown]; changed: [] }>()
const { data, text, skill, attachments, references, selected, transcript, error, limitError, busy, uploading, loading, pending, editable, activeTurn, locked, canSend, canNewConversation, refresh, send, newConversation, retry, archive, complete, stop, add, receive, modify, toggle, toggleGroup, fail } = useStudio(() => props.task, reason => emit('failure', reason), () => emit('changed'), undefined, props.actorId)
const expanded = ref(false), materialsOpen = ref(true), dragging = ref(false), input = ref<HTMLInputElement>(), archiveOpen = ref(false), completeOpen = ref(false), conversationOpen = ref(false), sku = ref('')
const workspace = ref<HTMLElement>(), workspaceHeight = ref('calc(100dvh - 230px)')
let resizeObserver: ResizeObserver | undefined
function fitWorkspace() {
  if (expanded.value) return
  const card = workspace.value?.querySelector('.studio-chat-card')
  if (card) workspaceHeight.value = `${Math.max(300, window.innerHeight - card.getBoundingClientRect().top - 14)}px`
}
onMounted(() => { resizeObserver = new ResizeObserver(fitWorkspace); if (workspace.value?.parentElement) resizeObserver.observe(workspace.value.parentElement); window.addEventListener('resize', fitWorkspace); fitWorkspace() })
watch(expanded, () => { void nextTick(fitWorkspace) })
const hasArchive = computed(() => data.value?.turns.some(t => t.pictures.some(p => p.archived)))
function drop(event: DragEvent) { dragging.value = false; const id = event.dataTransfer?.getData('application/x-studio-material'); if (id) add([id]); else void receive(Array.from(event.dataTransfer?.files || [])) }
function paste(event: ClipboardEvent) { const files = Array.from(event.clipboardData?.files || []); if (files.length) { event.preventDefault(); void receive(files) } }
function upload(event: Event) { const target = event.target as HTMLInputElement; void receive(Array.from(target.files || [])); target.value = '' }
async function doArchive() { if (await archive(sku.value)) archiveOpen.value = false }
async function doNewConversation() { if (await newConversation()) conversationOpen.value = false }
async function doComplete() { if (await complete()) completeOpen.value = false }
onUnmounted(() => { resizeObserver?.disconnect(); window.removeEventListener('resize', fitWorkspace) })
</script>
