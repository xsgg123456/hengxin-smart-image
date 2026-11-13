<template>
  <section class="hx-page domestic-studio" :class="{ 'is-expanded': expanded, 'has-tutorial': tutorialOpen && !narrow, 'has-sessions': conversationsOpen && !mobile }">
    <div class="hx-heading studio-page-heading">
      <div><span class="hx-admin-kicker">AI IMAGE WORKSPACE</span><h1>{{ config.title }}</h1><p>{{ config.description }}</p></div>
      <div class="studio-heading-actions"><ElButton :icon="Reading" :type="tutorialOpen ? 'primary' : 'default'" plain :aria-expanded="tutorialOpen" @click="toggleTutorial">使用教程</ElButton><ElButton :icon="Plus" :disabled="state.conversations.length >= 10" @click="newConversation">新建会话</ElButton></div>
    </div>
    <div class="domestic-studio-card">
      <header class="domestic-studio-toolbar">
        <div class="studio-identity"><span class="studio-ai-icon"><ElIcon><MagicStick /></ElIcon></span><strong>AI 设计工作台</strong><span class="studio-ready"><i></i>{{ runningCount ? `${runningCount} 个会话处理中` : '准备就绪' }}</span></div>
        <div class="studio-toolbar-actions"><ElButton :icon="ChatDotRound" :type="conversationsOpen ? 'primary' : 'default'" plain size="small" @click="toggleConversations">会话 · {{ state.conversations.length }}</ElButton><ElButton :icon="FolderOpened" :type="materialsOpen ? 'primary' : 'default'" plain size="small" @click="toggleMaterials">素材<span v-if="current.assets.length"> · {{ current.assets.length }}</span></ElButton><ElButton :icon="FullScreen" size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开' }}</ElButton></div>
      </header>
      <div class="domestic-studio-body">
        <aside v-if="conversationsOpen && !mobile" class="domestic-session-sidebar"><SessionPanel :sessions="state.conversations" :active-id="current.id" @close="conversationsOpen = false" @create="newConversation" @select="selectConversation" @action="sessionAction" /></aside>
        <div class="studio-main">
          <header class="domestic-current-session"><div><strong>{{ current.name }}</strong><small>独立会话 · 切换会保留附件和草稿</small></div><div class="session-archive-actions"><ElTag v-if="busy" size="small" type="primary">正在回复</ElTag><template v-if="!replacing"><ElButton size="small" :disabled="busy || !current.messages.some(message => message.role === 'assistant')" @click="archiveOpen = true">归档到成品库</ElButton><ElButton text size="small" @click="router.push(libraryPath)">查看成品库</ElButton></template></div></header>
          <div ref="transcript" class="studio-transcript" aria-live="polite">
            <MessageItem v-for="message in current.messages" :key="message.id" :message="message" @preview="preview" />
            <article v-if="busy" class="domestic-chat-message assistant"><div class="domestic-message-name">Codex<small>执行中</small></div><div class="domestic-message-bubble"><p class="thinking">正在整理你的要求<span>…</span></p></div></article>
          </div>
          <div class="studio-input-area" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="drop" @paste="paste">
            <ElAlert v-if="!activeSkill" title="该工作台暂不可用，请联系管理员配置。" type="warning" :closable="false" />
            <div v-if="current.pending.length" class="studio-pending"><div v-for="asset in current.pending" :key="asset.id"><img v-if="asset.image" :src="asset.url" :alt="asset.name"><ElIcon v-else><Document /></ElIcon><span>{{ asset.name }}<small>{{ asset.role }}</small></span><button :aria-label="`移除${asset.name}`" @click="current.pending = current.pending.filter(item => item.id !== asset.id)">×</button></div></div>
            <ElInput v-model="current.draft" type="textarea" :rows="3" resize="none" aria-label="设计要求" :placeholder="config.placeholder" @keydown="keydown" />
            <div class="studio-compose-actions"><div><ElButton text :icon="Paperclip" @click="choose(config.primaryRole)">上传附件</ElButton><span class="upload-help">拖拽或粘贴图片到这里</span></div><div><ElButton text :icon="EditPen" @click="editorOpen = true">展开编辑</ElButton><ElButton v-if="busy" @click="stop">停止</ElButton><ElButton v-else type="primary" :disabled="!activeSkill || (!current.draft.trim() && !current.pending.length)" :icon="Promotion" @click="send">发送</ElButton></div></div>
            <div v-if="dragging" class="drop-overlay">松开添加附件</div>
          </div>
          <div class="studio-input-footnote"><span>发送到：{{ current.name }} · Enter 发送，Shift + Enter 换行</span><span>交互预览 · 不调用真实生成</span></div>
        </div>
        <aside v-if="materialsOpen" class="studio-materials"><div class="panel-title"><strong>当前对话素材 <small>{{ current.assets.length }}</small></strong><ElButton text :icon="Close" aria-label="收起素材" @click="materialsOpen = false" /></div><p class="material-intro">本次上传的图片和文件都在这里。</p><div v-if="!current.assets.length" class="materials-empty"><ElIcon><FolderOpened /></ElIcon><p>还没有添加素材</p><small>上传后可随时查看和引用</small></div><div v-for="asset in current.assets" :key="asset.id" class="material-item"><button @click="preview(asset)"><img v-if="asset.image" :src="asset.url" :alt="asset.name"><ElIcon v-else><Document /></ElIcon></button><div><strong>{{ asset.name }}</strong><small>{{ asset.role }}</small><ElButton text type="primary" size="small" @click="reference(asset)">引用</ElButton></div></div><ElButton class="material-add" :icon="Plus" @click="choose(config.secondaryRole)">添加素材</ElButton></aside>
        <aside v-if="tutorialOpen && !narrow" class="studio-tutorial"><TutorialPanel :config="config" @close="closeTutorial" @use-example="useTutorialExample" /></aside>
      </div>
    </div>
    <ElDrawer v-if="mobile" v-model="conversationsOpen" :with-header="false" title="会话列表" size="min(300px, 90vw)" direction="ltr" class="session-drawer" append-to-body><SessionPanel :sessions="state.conversations" :active-id="current.id" @close="conversationsOpen = false" @create="newConversation" @select="selectConversation" @action="sessionAction" /></ElDrawer>
    <ArchiveDialog v-if="!replacing" v-model="archiveOpen" :config="config" :conversation="current" />
    <input ref="fileInput" type="file" hidden multiple @change="filesChanged">
    <ElDrawer v-if="narrow" v-model="tutorialOpen" :with-header="false" title="使用教程" size="min(460px, 100vw)" class="tutorial-drawer" append-to-body><TutorialPanel :config="config" @close="closeTutorial" @use-example="useTutorialExample" /></ElDrawer>
    <ElDialog v-model="editorOpen" title="编辑设计要求" width="min(760px,94vw)"><ElInput v-model="current.draft" type="textarea" :rows="12" aria-label="完整设计要求" /><template #footer><ElButton type="primary" @click="editorOpen = false">完成编辑</ElButton></template></ElDialog>
    <ElDialog v-model="imageOpen" :title="imageTitle" width="min(860px,94vw)"><img class="asset-preview" :src="imageUrl" :alt="imageTitle"></ElDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Close, MagicStick, ChatDotRound, FolderOpened, FullScreen, Paperclip, EditPen, Promotion, Document, Reading } from '@element-plus/icons-vue'
import { useWindowSize } from '@vueuse/core'
import { states, previewActor, tutorialOpen, createConversation, startDemoReply, stopDemoReply, type Asset, type Conversation } from './state'
import { workspaces } from './workspaces'
import TutorialPanel from './TutorialPanel.vue'
import './tutorial.css'
import SessionPanel from './SessionPanel.vue'
import './sessions.css'
import './library.css'
import ArchiveDialog from './ArchiveDialog.vue'
import MessageItem from './MessageItem.vue'
import { libraryPath } from './archives'
import { boundSkill } from './skills-state'
const route = useRoute(), router = useRouter(), archiveOpen = ref(false)
const config = computed(() => workspaces.find(item => item.path === route.path) || workspaces[0])
const { width } = useWindowSize()
const narrow = computed(() => width.value < 1450)
const mobile = computed(() => width.value < 800)
const replacing = computed(() => config.value.group === 'replace')
const activeSkill = computed(() => boundSkill(config.value.id))
const state = computed(() => states[config.value.id])
const current = computed(() => state.value.conversations[state.value.active])
const conversationsOpen = ref(!mobile.value), materialsOpen = ref(false), expanded = ref(false), editorOpen = ref(false), dragging = ref(false)
const busy = computed(() => current.value.running)
const runningCount = computed(() => state.value.conversations.filter(item => item.running).length)
const fileInput = ref<HTMLInputElement>(), transcript = ref<HTMLElement>(), uploadRole = ref('产品资料'), imageOpen = ref(false), imageUrl = ref(''), imageTitle = ref('')
function openTutorial() { tutorialOpen.value = true; materialsOpen.value = false; if (mobile.value) conversationsOpen.value = false }
function closeTutorial() { tutorialOpen.value = false }
function toggleTutorial() { if (tutorialOpen.value) closeTutorial(); else openTutorial() }
function toggleMaterials() { materialsOpen.value = !materialsOpen.value; if (materialsOpen.value) tutorialOpen.value = false }
function toggleConversations() { conversationsOpen.value = !conversationsOpen.value; if (conversationsOpen.value && narrow.value) tutorialOpen.value = false }
function useTutorialExample(text: string) { current.value.draft = current.value.draft.trim() ? `${current.value.draft}\n\n${text}` : text; if (narrow.value) closeTutorial(); ElMessage.success('已填入输入框，检查后再发送') }
function choose(role: string) { uploadRole.value = role; fileInput.value?.click() }
function receive(files: File[]) { for (const file of files) { if (file.size > 20 * 1024 * 1024) { ElMessage.warning(`${file.name} 超过预览的 20 MB 限制`); continue } const asset: Asset = { id: Date.now() + Math.random(), name: file.name, url: URL.createObjectURL(file), image: file.type.startsWith('image/'), role: uploadRole.value }; current.value.assets.push(asset); current.value.pending.push(asset) } }
function filesChanged(event: Event) { const input = event.target as HTMLInputElement; receive(Array.from(input.files || [])); input.value = '' }
function drop(event: DragEvent) { dragging.value = false; uploadRole.value = config.value.primaryRole; receive(Array.from(event.dataTransfer?.files || [])) }
function paste(event: ClipboardEvent) { if (event.clipboardData?.files.length) { event.preventDefault(); uploadRole.value = config.value.primaryRole; receive(Array.from(event.clipboardData.files)) } }
function reference(asset: Asset) { if (!current.value.pending.some(item => item.id === asset.id)) current.value.pending.push(asset); ElMessage.success('已加入本轮附件') }
function preview(asset: Asset) { if (!asset.image) { ElMessage.info(`文件：${asset.name}（本地预览）`); return } imageUrl.value = asset.url; imageTitle.value = asset.name; imageOpen.value = true }
function keydown(event: Event | KeyboardEvent) { if (event instanceof KeyboardEvent && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send() } }
function send() {
  if (!activeSkill.value) { ElMessage.warning('该工作台暂不可用，请联系管理员配置'); return }
  if (busy.value || (!current.value.draft.trim() && !current.value.pending.length)) return
  const conversation = current.value, selectedConfig = config.value
  const text = conversation.draft.trim() || '请根据这些资料开始处理。'
  if (!conversation.messages.length && !conversation.renamed) conversation.name = text.slice(0, 16)
  conversation.messages.push({ id: Date.now(), role: 'user', text, createdAt: new Date().toISOString(), actorName: previewActor.name, actorId: previewActor.id, skill: { id: activeSkill.value.id, name: activeSkill.value.name }, files: [...conversation.pending] })
  conversation.draft = ''; conversation.pending = []
  startDemoReply(conversation, `已收到「${selectedConfig.title}」要求${conversation.assets.length ? `和 ${conversation.assets.length} 份资料` : ''}。\n\n${selectedConfig.reply}\n\n这是交互演示回复，尚未调用模型或生成图片。你可以继续输入修改意见，体验连续对话。`)
  scroll()
}
function scroll() { void nextTick(() => transcript.value?.scrollTo({ top: current.value.messages.length ? transcript.value.scrollHeight : 0, behavior: 'smooth' })) }
function stop() { stopDemoReply(current.value) }
function newConversation() {
  if (state.value.conversations.length >= 10) return
  state.value.conversations.push(createConversation(`新会话 ${state.value.nextSerial++}`))
  state.value.active = state.value.conversations.length - 1
  conversationsOpen.value = !mobile.value
}
function selectConversation(conversation: Conversation) {
  const index = state.value.conversations.findIndex(item => item.id === conversation.id)
  if (index < 0) return
  state.value.active = index
  if (mobile.value) conversationsOpen.value = false
}
function sessionAction(command: string, conversation: Conversation) {
  if (command === 'rename') void rename(conversation)
  if (command === 'delete') void removeConversation(conversation)
}
async function rename(conversation: Conversation) {
  try {
    const { value } = await ElMessageBox.prompt('名称只用于区分会话，不影响已有内容。', '重命名会话', { inputValue: conversation.name, inputValidator: value => !!value?.trim() && value.trim().length <= 30 || '请输入 1–30 个字', confirmButtonText: '保存', cancelButtonText: '取消' })
    conversation.name = value.trim(); conversation.renamed = true
  } catch { /* cancelled */ }
}
async function removeConversation(conversation: Conversation) {
  const owner = state.value
  if (conversation.running) return
  try {
    await ElMessageBox.confirm(`删除「${conversation.name}」及其对话、附件和草稿，无法恢复。其他会话不受影响。${owner.conversations.length === 1 ? '删除后将打开一个新的空白会话。' : ''}`, '删除会话', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
    if (conversation.running) { ElMessage.warning('请先停止该会话，再删除。'); return }
    const index = owner.conversations.findIndex(item => item.id === conversation.id)
    if (index < 0) return
    const activeId = owner.conversations[owner.active]?.id
    stopDemoReply(conversation)
    conversation.assets.forEach(asset => URL.revokeObjectURL(asset.url))
    owner.conversations.splice(index, 1)
    if (!owner.conversations.length) owner.conversations.push(createConversation(`新会话 ${owner.nextSerial++}`))
    const retainedIndex = owner.conversations.findIndex(item => item.id === activeId)
    owner.active = retainedIndex >= 0 ? retainedIndex : Math.min(index, owner.conversations.length - 1)
    ElMessage.success('会话已删除，其他会话保留')
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(`删除未完成：${error instanceof Error ? error.message : String(error)}`) }
}
watch(() => route.path, () => { archiveOpen.value = false; conversationsOpen.value = !mobile.value; materialsOpen.value = false; expanded.value = false; editorOpen.value = false; imageOpen.value = false })
watch(() => current.value.id, () => { archiveOpen.value = false; editorOpen.value = false; imageOpen.value = false; scroll() })
watch(() => current.value.messages.length, scroll)
watch(mobile, value => { conversationsOpen.value = !value })

</script>
