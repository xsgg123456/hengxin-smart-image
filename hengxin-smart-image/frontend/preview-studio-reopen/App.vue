<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <ArchiveLibrary v-show="isLibrary" :pictures="savedPictures" :events="events" @studio="goStudio" />
    <div v-show="!isLibrary" class="hx-page preview-task reopen-preview">
      <div class="hx-heading"><div><h1>直杆实木布罩灯-乡村风</h1><p>直杆实木布罩灯-乡村风 · OUTON · Amazon · 美国/英语 · 负责设计：张帅</p></div><div class="studio-actions"><ElButton size="small" @click="refresh">刷新任务详情</ElButton><ElButton size="small" @click="listOpen = true">返回任务列表</ElButton></div></div>
      <div class="preview-note">交互预览 · 示例数据 · 可体验完成、解冻与原对话续聊，刷新页面重置</div>
      <div class="studio-page">
        <div class="studio-steps" aria-label="工作流进度">
          <span :class="completed ? 'finished' : 'done'">{{ completed ? '✓' : '①' }} 运营提交图需</span><i></i>
          <span :class="completed ? 'finished' : 'done'">{{ completed ? '✓' : '②' }} 设计人工审核</span><i></i>
          <span :class="completed ? 'finished' : 'active'">{{ completed ? '✓' : '③' }} AI 设计工作台<small v-if="reopened && !completed">继续设计</small></span><i></i>
          <span class="finished">{{ completed ? '✓' : '④' }} 归档成品库<small v-if="!completed">已有归档</small></span>
          <ElTag v-if="completed" type="success" size="small">全部完成</ElTag>
        </div>
        <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }" @keydown.esc="expanded = false">
          <div class="studio-chat-heading"><strong>与 Codex 协作{{ completed ? ' · 已完成' : reopened ? ' · 继续设计' : '' }}</strong><div class="studio-actions">
            <ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ materials.length }}</ElButton>
            <ElButton size="small" @click="refresh">刷新</ElButton>
            <ElButton size="small" :disabled="completed || running" @click="newOpen = true">开始新对话</ElButton>
            <ElButton v-if="!completed" size="small" type="primary" :disabled="!selected.length || running" @click="archiveOpen = true">归档成品（{{ selected.length }}）</ElButton>
            <ElButton size="small" @click="goLibrary">查看归档成品</ElButton>
            <ElButton v-if="completed" size="small" type="primary" @click="reopenOpen = true">解冻工作台</ElButton>
            <ElButton v-else size="small" :disabled="running" @click="completeOpen = true">完成任务</ElButton>
            <ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton>
          </div></div>
          <div class="studio-workspace"><section class="studio-conversation">
            <div ref="chat" class="studio-messages">
              <div class="studio-conversation-divider">{{ conversationNumber === 1 ? '当前对话' : `当前为新对话 ${conversationNumber} · 以下保留历史记录` }}</div>
              <template v-for="turn in turns" :key="turn.id">
                <article class="studio-message user"><div class="studio-message-name">设计师</div><div class="studio-bubble"><p>{{ turn.text }}</p></div></article>
                <ProcessReply :turn="turn" :selected="selected" :archived="archived" :disabled="completed || running" @toggle="toggle" @group="group" @modify="modify" />
              </template>
            </div>
            <div class="studio-composer" @dragover.prevent @drop.prevent="drop">
              <p v-if="completed" class="completion-note">任务已完成。需要继续修改时，点击右上方“解冻工作台”。</p>
              <button class="studio-dropzone" :disabled="completed || running" @click="explain">拖拽图片或文件到这里，或点击上传 <small>最多 100 个附件 · 单个最大 500 MB</small></button>
              <Attachments v-if="pending.length" :assets="pending" title="本轮引用素材" compact />
              <ElInput v-model="text" :disabled="completed || running" type="textarea" :rows="2" resize="none" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown="onSendKey" />
              <div class="studio-compose-tools"><ElSelect v-model="skill" :disabled="completed || running" aria-label="选择 Skill" placeholder="选择 Skill（可选）" style="width:265px"><ElOption label="OUTON 亚马逊新品整套主图生成" value="outon" /></ElSelect><ElButton v-if="running" @click="stop">停止</ElButton><ElButton v-else type="primary" :disabled="completed || (!text.trim() && !pending.length)" @click="send">发送</ElButton></div>
              <p class="studio-compose-note">支持 JPG/PNG/WebP、PDF/DOCX/PPTX/XLS/XLSX/CSV/TXT · Enter 发送，Shift + Enter 换行（兼容 Ctrl + Enter）。</p>
            </div>
          </section><Materials v-if="materialsOpen" :assets="materials" :disabled="completed || running" @close="materialsOpen = false" @add="add" /></div>
        </ElCard>
      </div>
    </div>
    <ElDialog v-model="completeOpen" title="确认完成任务" width="min(480px,94vw)" append-to-body><p>完成后工作台将锁定，已归档成品和对话记录都会保留。</p><p>后续需要修改，可以解冻工作台，继续当前对话。</p><template #footer><ElButton @click="completeOpen = false">继续设计</ElButton><ElButton type="primary" @click="completeTask">确认完成</ElButton></template></ElDialog>
    <ElDialog v-model="reopenOpen" title="解冻工作台" width="min(480px,94vw)" append-to-body><p>解冻后任务回到第③步“AI 设计工作台”，恢复为设计中。</p><p>继续使用原来的对话，聊天记录、素材和已归档成品全部保留。</p><template #footer><ElButton @click="reopenOpen = false">取消</ElButton><ElButton type="primary" @click="reopenTask">确认解冻</ElButton></template></ElDialog>
    <ElDialog v-model="newOpen" title="开始新对话" width="min(480px,94vw)" append-to-body><p>将开始新的对话上下文。旧对话、任务素材和归档成品保留。</p><p>如果要接着原来的内容修改，请取消并直接发送意见。</p><template #footer><ElButton @click="newOpen = false">取消</ElButton><ElButton type="primary" @click="startNew">确认开始新对话</ElButton></template></ElDialog>
    <ElDialog v-model="listOpen" title="工作流任务 · 预览" width="min(740px,94vw)" append-to-body><div class="preview-list-row"><strong>直杆实木布罩灯-乡村风</strong><ElTag :type="completed ? 'success' : 'primary'">{{ completed ? '已完成' : 'AI 设计工作台' }}</ElTag><ElButton @click="listOpen = false">查看任务</ElButton></div></ElDialog>
    <ArchiveConfirm :open="archiveOpen" :pictures="selectedPictures" @close="archiveOpen = false" @confirm="confirmArchive" />
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import Attachments from '../preview-studio-images/Attachments.vue'
import Materials from './Materials.vue'
import ProcessReply from './ProcessReply.vue'
import { materials as sampleMaterials } from '../preview-studio-process/fixtures'
import { useProcessPreview } from '../preview-studio-process/state'
import ArchiveLibrary from '../preview-studio-process/ArchiveLibrary.vue'
import ArchiveConfirm from '../preview-studio-process/ArchiveConfirm.vue'
import { useArchivePreview } from '../preview-studio-process/archive-state'
import { handleSendKey } from '../preview-studio-process/send-key'
const materials = sampleMaterials.slice(0, 7)
const completed = ref(true), reopened = ref(false), expanded = ref(false), materialsOpen = ref(true), skill = ref('')
const completeOpen = ref(false), reopenOpen = ref(false), archiveOpen = ref(false), newOpen = ref(false), listOpen = ref(false)
const conversationNumber = ref(1)
const { turns, selected, archived, text, chat, pending, running, play, stop, toggle, group, add, modify } = useProcessPreview()
const route = useRoute(), router = useRouter()
const isLibrary = computed(() => route.path === '/overseas/archive')
const { pictures: savedPictures, events, save } = useArchivePreview()
archived.value = savedPictures.value.map(p => p.id)
const selectedPictures = computed(() => turns.value.flatMap(t => t.pictures).filter(p => selected.value.includes(p.id)))
function explain() { ElMessage.info('独立交互预览，使用示例资料，不连接真实业务或 AI。') }
function refresh() { ElMessage.success('已显示当前预览状态') }
function goLibrary() { expanded.value = false; void router.push('/overseas/archive') }
function goStudio() { void router.push('/preview-studio-reopen/index.html') }
function completeTask() { if (running.value) return; completed.value = true; selected.value = []; completeOpen.value = false; ElMessage.success('任务已完成，归档成品和对话记录已保留') }
function reopenTask() { completed.value = false; reopened.value = true; reopenOpen.value = false; ElMessage.success('已解冻，继续使用原来的对话') }
function startNew() { if (completed.value || running.value) return; conversationNumber.value++; text.value = ''; pending.value = []; selected.value = []; skill.value = ''; newOpen.value = false; ElMessage.info('已切换为新的模拟对话上下文，历史内容保留') }
function confirmArchive() { if (completed.value || !selectedPictures.value.length) return; save(selectedPictures.value); archived.value = [...new Set([...archived.value, ...selected.value])]; selected.value = []; archiveOpen.value = false; ElMessage.success('已追加归档，原有成品保留') }
function send() { if (!completed.value && !running.value && (text.value.trim() || pending.value.length)) play(true) }
function onSendKey(event: Event | KeyboardEvent) { if (event instanceof KeyboardEvent) handleSendKey(event, send) }
function drop(event: DragEvent) { if (completed.value || running.value) return; const id = event.dataTransfer?.getData('application/x-preview-material'); if (id) add(materials.filter(a => a.id === id)); else explain() }
</script>
