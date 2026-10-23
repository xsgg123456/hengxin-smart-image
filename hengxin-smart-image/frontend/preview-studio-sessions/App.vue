<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="hx-page preview-task sessions-preview">
      <div class="hx-heading"><div><h1>{{ taskName }}</h1><p>{{ taskName }} · OUTON · Amazon · 美国/英语 · 负责设计：张帅</p></div><div class="studio-actions"><ElButton size="small" @click="explain">刷新任务详情</ElButton><ElButton size="small" @click="explain">返回任务列表</ElButton></div></div>
      <div class="sessions-demo"><span>预览状态</span><ElButtonGroup aria-label="预览状态切换"><ElButton size="small" :type="!completed ? 'primary' : 'default'" @click="previewState('design')">设计中</ElButton><ElButton size="small" :type="completed && !reopenOpen ? 'primary' : 'default'" @click="previewState('completed')">已完成</ElButton><ElButton size="small" :type="reopenOpen ? 'primary' : 'default'" @click="previewState('reopen')">解冻确认</ElButton></ElButtonGroup><span>交互预览 · 示例数据 · 约 30 秒模拟生成 · 刷新重置</span><ElButton text size="small" :disabled="!running(current)" @click="finish(current)">模拟当前生成完成</ElButton><ElButton text size="small" :disabled="!running(current)" @click="finish(current, 'failed')">模拟当前失败</ElButton></div>
      <div class="studio-steps" :class="{ 'session-steps-completed': completed }"><span class="done">① 运营提交图需</span><i /><span class="done">② 设计人工审核</span><i /><span class="active">③ AI 设计工作台</span><i /><span>{{ completed ? '✓ 已归档 · 任务完成' : '④ 归档成品库' }}</span></div>
      <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }" @keydown.esc="expanded = false">
        <div class="studio-chat-heading"><div class="session-heading"><strong>与 Codex 协作</strong><span v-if="runningCount" role="status">{{ runningCount }} 个会话执行中</span><ElTag v-if="completed" type="success" size="small">任务已完成</ElTag></div><div class="studio-actions">
          <ElButton size="small" @click="sessionsOpen = !sessionsOpen">会话 · {{ sessions.length }}/10</ElButton><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ taskMaterials.length }}</ElButton><ElButton size="small" @click="explain">刷新</ElButton>
          <ElButton size="small" @click="libraryOpen = true">查看本任务成品（{{ archived.length }}）</ElButton><ElButton v-if="!completed" size="small" :disabled="!!runningCount || !archived.length" :title="runningCount ? '请等待或停止所有执行后完成任务' : '至少归档一张图片后可完成'" @click="completeTask">完成任务</ElButton><ElButton v-else size="small" type="primary" @click="reopenOpen = true">解冻工作台</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton>
        </div></div>
        <div v-if="completed" class="session-completed-notice" role="status"><strong>任务已完成 · 所有会话只读</strong><span>可切换查看历史及归档成品。需要继续设计，请点击“解冻工作台”。</span></div><div class="studio-workspace">
          <SessionList v-if="sessionsOpen" :sessions="sessions" :active-id="activeId" :completed="completed" :running="running" :label="label" @select="selectSession" @create="newSession" @close="sessionsOpen = false" @action="action" />
          <section class="studio-conversation">
            <div class="session-current"><div><strong>{{ current.name }}</strong><small>{{ completed ? '只读会话 · 历史记录与文件保留' : running(current) ? '生成中 · 切换会话不中断执行' : '独立上下文 · 独立工作文件' }}</small></div><ElButton text size="small" @click="action('rename', current)" :disabled="completed">重命名</ElButton></div>
            <div ref="chat" class="studio-messages" @scroll="saveScroll">
              <div v-if="!current.turns.length" class="studio-empty"><div class="studio-mark"><ElIcon :size="25"><ChatDotRound /></ElIcon></div><h2>{{ completed ? '该会话暂无历史记录' : `开始 ${current.name}` }}</h2><p v-if="completed">当前任务已完成，解冻后可继续在此会话设计。</p><p v-else>描述这次要做的设计，或引用右侧任务素材。<br>这个会话有独立上下文，不会带入其他会话的内容。</p></div>
              <template v-for="turn in current.turns" :key="turn.id"><article class="studio-message user"><div class="studio-message-name">设计师</div><div class="studio-bubble"><p>{{ turn.text }}</p></div></article><ProcessReply :turn="turn" :selected="current.selected" :archived="archived.map(a => a.asset.id)" :disabled="completed" @toggle="toggle" @group="group" @modify="modify" /></template>
            </div>
            <div class="session-archive-bar"><span>{{ completed ? '成品已归入本任务，可通过右上角查看' : current.selected.length ? `已选当前会话 ${current.selected.length} 张图片` : '勾选当前会话图片，归档到本任务' }}</span><ElButton size="small" type="primary" :disabled="completed || !selectedPictures.length" @click="archiveOpen = true; sku = ''">归档所选图片（{{ selectedPictures.length }}）</ElButton></div>
            <div class="studio-composer" @dragover.prevent @drop.prevent="drop">
              <input ref="fileInput" type="file" multiple hidden @change="upload" />
              <button class="studio-dropzone" :disabled="completed" @click="fileInput?.click()">拖拽图片或文件到这里，或点击上传 <small>仅加入当前会话</small></button>
              <Attachments :assets="current.attachments" title="当前会话引用" compact :removable="!completed" @remove="id => { if (!completed) current.attachments = current.attachments.filter(a => a.id !== id) }" />
              <ElInput v-model="current.draft" :disabled="completed" type="textarea" :rows="2" resize="none" aria-label="设计要求" :placeholder="completed ? '任务已完成，解冻后可继续发送…' : running(current) ? '可先写下一条要求，当前生成结束后再发送…' : '描述设计要求，或继续提出修改意见…'" @keydown="keySend" />
              <div class="studio-compose-tools"><ElSelect v-model="current.skill" :disabled="completed" aria-label="选择 Skill" placeholder="选择 Skill（可选）" clearable><ElOption label="OUTON 亚马逊新品整套主图生成" value="outon" /><ElOption label="电商详情页设计" value="detail" /></ElSelect><ElButton v-if="running(current)" @click="finish(current, 'cancelled')">停止当前生成</ElButton><ElButton v-else type="primary" :disabled="completed || (!current.draft.trim() && !current.attachments.length)" @click="sendMessage">发送</ElButton></div>
              <p class="studio-compose-note">发送到：{{ current.name }} · Enter 发送，Shift + Enter 换行 · 切换会话保留草稿</p>
            </div>
          </section>
          <StudioMaterials v-if="materialsOpen" :key="activeId" :assets="taskMaterials" :disabled="completed" @close="materialsOpen = false" @add="reference" @remove="a => removeMaterials([a.id])" @remove-selected="removeMaterials" @failure="explain" />
        </div>
      </ElCard>
    </div>
    <ElDialog v-model="reopenOpen" title="解冻当前任务的工作台？" width="min(520px,94vw)" append-to-body>
      <p class="session-reopen-task">{{ taskName }}</p>
      <p>解冻后，本任务全部 <strong>{{ sessions.length }}</strong> 个会话恢复编辑，可以继续设计。</p>
      <p class="session-dialog-note">原会话、上下文、草稿和 {{ archived.length }} 张已归档成品保留。不会自动开始生成，也不需要重新提交图需或审核。</p>
      <template #footer><ElButton @click="reopenOpen = false">取消</ElButton><ElButton type="primary" @click="confirmReopen">确认解冻</ElButton></template>
    </ElDialog>
    <ElDialog v-model="archiveOpen" title="归档所选图片" width="min(620px,94vw)" append-to-body><p>归属任务：<strong>{{ taskName }}</strong></p><p>来源会话：<strong>{{ current.name }}</strong> · {{ selectedPictures.length }} 张图片</p><div class="studio-archive-thumbs"><img v-for="p in selectedPictures" :key="p.id" :src="p.url" :alt="p.name" /></div><ElSelect v-model="sku" aria-label="选择所属 SKU" placeholder="选择本任务 SKU" style="width:100%"><ElOption label="H-ZGD0008" value="H-ZGD0008" /></ElSelect><p class="session-dialog-note">各会话的成品统一归入本任务，保留来源会话。此处仅模拟归档。</p><template #footer><ElButton @click="archiveOpen = false">取消</ElButton><ElButton type="primary" :disabled="!sku" @click="confirmArchive">确认归档</ElButton></template></ElDialog>
    <ElDialog v-model="libraryOpen" title="本任务归档成品" width="min(850px,94vw)" append-to-body><p>{{ taskName }}</p><ElSelect v-model="sourceFilter" aria-label="筛选来源会话" placeholder="全部会话"><ElOption label="全部会话" value="" /><ElOption v-for="s in archiveSources" :key="s.id" :label="s.name" :value="s.id" /></ElSelect><ElEmpty v-if="!filteredArchive.length" description="暂无归档成品，请先在会话内勾选图片归档" /><div class="session-library"><article v-for="a in filteredArchive" :key="a.asset.id"><AssetImage :asset="a.asset" :group="filteredArchive.map(x => x.asset)" title="本任务归档成品" /><strong>{{ a.asset.name }}</strong><small>来源：{{ a.sessionName }}</small><small>SKU：{{ a.sku }}</small></article></div></ElDialog>
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound } from '@element-plus/icons-vue'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import StudioMaterials from '@/views/overseas/studio/StudioMaterials.vue'
import ProcessReply from '../preview-studio-reopen/ProcessReply.vue'
import Attachments from '../preview-studio-images/Attachments.vue'
import AssetImage from '../preview-studio-images/AssetImage.vue'
import SessionList from './SessionList.vue'
import { taskName, useSessions } from './state'
import type { Session } from './state'
import type { Asset } from '../preview-studio-images/state'
import type { Asset as TaskAsset } from '@/api/overseas/studio'
const { sessions, current, activeId, completed, archived, running, runningCount, selectedPictures, switchTo, create, finish, send, remove, add, toggle, group, archive, previewCompleted, label, materials } = useSessions()
const sessionsOpen = ref(true), materialsOpen = ref(true), expanded = ref(false), archiveOpen = ref(false), libraryOpen = ref(false), sku = ref(''), sourceFilter = ref('')
const reopenOpen = ref(false)
const chat = ref<HTMLElement>(), fileInput = ref<HTMLInputElement>()
const taskMaterials = ref<TaskAsset[]>(materials.slice(0, 2).map((a, i) => ({ id: a.id, name: a.name, contentType: a.image ? 'image/jpeg' : 'text/plain', sizeBytes: i ? 573200 : 42100, url: a.url, source: 'task' })))
const archiveSources = computed(() => [...new Map(archived.value.map(a => [a.sessionId, { id: a.sessionId, name: a.sessionName }])).values()])
const filteredArchive = computed(() => archived.value.filter(a => !sourceFilter.value || a.sessionId === sourceFilter.value))
function explain() { ElMessage.info('独立交互预览，示例数据不连接真实业务；刷新页面会重置。') }
function previewState(state: 'design' | 'completed' | 'reopen') {
  archiveOpen.value = false; libraryOpen.value = false; reopenOpen.value = false
  if (state === 'design') completed.value = false
  else { previewCompleted(); reopenOpen.value = state === 'reopen'; ElMessage.info('已切换示例状态：模拟生成已结束，缺少归档时自动补充示例成品。') }
}
function confirmReopen() { completed.value = false; reopenOpen.value = false; ElMessage.success('已解冻，全部会话恢复编辑，可继续原对话') }
function saveScroll() { if (chat.value) current.value.scroll = chat.value.scrollTop }
async function selectSession(s: Session) { saveScroll(); switchTo(s); await nextTick(); if (chat.value) chat.value.scrollTop = s.scroll }
async function newSession() { saveScroll(); create(); await nextTick(); if (chat.value) chat.value.scrollTop = 0 }
async function sendMessage() { send(); await nextTick(); if (chat.value) chat.value.scrollTop = chat.value.scrollHeight }
function keySend(e: Event | KeyboardEvent) { if (!(e instanceof KeyboardEvent)) return; if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); void sendMessage() } }
function reference(ids: string[]) { add(materials.filter(a => ids.includes(a.id))); ElMessage.success(`已引用到「${current.value.name}」`) }
function modify(a: Asset) { add([a]); current.value.draft = `请修改「${a.name}」：` }
async function action(command: string, s: Session) {
  if (completed.value) return
  try {
    if (command === 'rename') { const { value } = await ElMessageBox.prompt('名称只用于区分会话，不影响上下文。', '重命名会话', { inputValue: s.name, inputValidator: v => !!v?.trim() && v.trim().length <= 30 || '请输入 1–30 个字', confirmButtonText: '保存', cancelButtonText: '取消' }); s.name = value.trim(); for (const a of archived.value) if (a.sessionId === s.id) a.sessionName = s.name }
    else { if (running(s)) return; await ElMessageBox.confirm(`删除「${s.name}」及其历史、工作文件和未归档图片，已归档成品保留。${sessions.value.length === 1 ? '删除后将创建一个空白会话。' : '删除后释放一个会话名额。'}`, '删除会话', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }); remove(s) }
  } catch { /* dialog cancelled */ }
}
async function removeMaterials(ids: string[]) { try { await ElMessageBox.confirm('仅从任务素材列表移除，所有会话中已引用的文件保留。', '移除任务素材', { confirmButtonText: '确认移除', cancelButtonText: '取消', type: 'warning' }); taskMaterials.value = taskMaterials.value.filter(a => !ids.includes(a.id)) } catch { /* cancelled */ } }
async function completeTask() { try { await ElMessageBox.confirm('完成后所有会话锁定，已归档成品保留。', '完成当前工作流任务', { confirmButtonText: '确认完成', cancelButtonText: '取消' }); if (!runningCount.value && archived.value.length) completed.value = true } catch { /* cancelled */ } }
function confirmArchive() { archive(sku.value); archiveOpen.value = false; ElMessage.success('已归档到当前任务') }
const objectUrls: string[] = []
function receive(files: File[]) { if (completed.value) return; add(files.map(file => { const url = URL.createObjectURL(file); objectUrls.push(url); return { id: crypto.randomUUID(), name: file.name, url, image: file.type.startsWith('image/'), caption: '当前会话上传 · 本地预览' } })) }
function upload(e: Event) { const input = e.target as HTMLInputElement; receive(Array.from(input.files || [])); input.value = '' }
function drop(e: DragEvent) { const id = e.dataTransfer?.getData('application/x-studio-material'); if (id) reference([id]); else receive(Array.from(e.dataTransfer?.files || [])) }
onUnmounted(() => objectUrls.forEach(url => URL.revokeObjectURL(url)))
</script>


