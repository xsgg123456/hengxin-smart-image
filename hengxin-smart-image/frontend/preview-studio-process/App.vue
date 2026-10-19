<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <ArchiveLibrary v-show="isLibrary" :pictures="savedPictures" :events="events" @studio="goStudio" />
    <div v-show="!isLibrary" class="hx-page preview-task process-preview">
      <div class="hx-heading"><div><h1>直杆实木布罩灯-乡村风测试</h1><p>直杆实木布罩灯-乡村风 · OUTON · Amazon · 美国/英语 · 负责设计：张帅</p></div><div class="studio-actions"><ElButton size="small" @click="show('succeeded')">刷新任务详情</ElButton><ElButton size="small" @click="explain">返回任务列表</ElButton></div></div>
      <div class="studio-page">
        <div class="studio-steps"><span class="done">① 运营提交图需</span><i></i><span class="done">② 设计人工审核</span><i></i><span class="active">③ AI 设计工作台</span><i></i><span>④ 归档成品库</span></div>
        <div class="process-demo-bar" aria-label="预览状态切换"><span>交互预览 · 示例数据</span><ElButton size="small" type="primary" plain @click="play()">播放执行到完成</ElButton><ElButton size="small" @click="show('running')">查看执行中</ElButton><ElButton size="small" @click="show('succeeded')">查看已完成</ElButton><ElButton size="small" @click="show('succeeded', true)">查看多轮对话</ElButton><ElButton size="small" @click="show('failed')">查看失败状态</ElButton><ElButton size="small" @click="goLibrary">查看成品库</ElButton><ElButton v-if="running" size="small" @click="finish">立即完成演示</ElButton></div>
        <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }">
          <div class="studio-chat-heading"><strong>与 Codex 协作</strong><div class="studio-actions"><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ materials.length }}</ElButton><ElButton size="small" @click="show('succeeded')">刷新</ElButton><ElButton size="small" @click="explain">开始新对话</ElButton><ElButton size="small" type="primary" :disabled="!selected.length" @click="confirmOpen = true">归档成品（{{ selected.length }}）</ElButton><ElButton size="small" @click="explain">完成任务</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton></div></div>
          <div class="studio-workspace"><section class="studio-conversation">
            <div ref="chat" class="studio-messages">
              <div class="studio-conversation-divider">当前对话</div>
              <template v-for="turn in turns" :key="turn.id">
                <article class="studio-message user"><div class="studio-message-name">设计师</div><div class="studio-bubble"><ElTag size="small">OUTON 亚马逊新品整套主图生成</ElTag><p>{{ turn.text }}</p></div></article>
                <ProcessReply :turn="turn" :selected="selected" :archived="archived" @toggle="toggle" @group="group" @modify="modify" />
              </template>
            </div>
            <div class="studio-composer" @dragover.prevent @drop.prevent="drop">
              <button class="studio-dropzone" @click="explain">拖拽图片或文件到这里，或点击上传 <small>最多 100 个附件 · 单个最大 500 MB</small></button>
              <Attachments v-if="pending.length" :assets="pending" title="本轮引用素材" removable compact @remove="pending = pending.filter(a => a.id !== $event)" />
              <ElInput v-model="text" type="textarea" :rows="2" resize="none" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown="onSendKey" />
              <div class="studio-compose-tools"><ElSelect v-model="skill" aria-label="选择 Skill" placeholder="选择 Skill（可选）" style="width:265px"><ElOption label="选择 Skill（可选）" value="" /><ElOption label="OUTON 亚马逊新品整套主图生成" value="outon" /></ElSelect><ElButton v-if="running" @click="stop">停止执行</ElButton><ElButton v-else type="primary" :disabled="!text.trim() && !pending.length" @click="send">发送</ElButton></div>
              <p class="studio-compose-note">Enter 发送 · Shift + Enter 换行 · 也可点击发送按钮 · 本地预览，刷新后重置</p>
            </div>
          </section><Materials v-if="materialsOpen" :assets="materials" @close="materialsOpen = false" @add="add" /></div>
        </ElCard>
      </div>
    </div>
    <ArchiveConfirm :open="confirmOpen" :pictures="selectedPictures" @close="confirmOpen = false" @confirm="confirmArchive" />
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import Materials from '../preview-studio-images/Materials.vue'
import Attachments from '../preview-studio-images/Attachments.vue'
import ProcessReply from './ProcessReply.vue'
import { materials } from './fixtures'
import { useProcessPreview } from './state'
import ArchiveLibrary from './ArchiveLibrary.vue'
import ArchiveConfirm from './ArchiveConfirm.vue'
import { useArchivePreview } from './archive-state'
import { handleSendKey } from './send-key'
const expanded = ref(false), materialsOpen = ref(true), skill = ref('')
const { turns, selected, archived, text, chat, pending, running, show, play, finish, stop, toggle, group, explain, add, modify } = useProcessPreview()
const route = useRoute(), router = useRouter(), confirmOpen = ref(false)
const isLibrary = computed(() => route.path === '/overseas/archive')
const { pictures: savedPictures, events, save } = useArchivePreview()
const selectedPictures = computed(() => turns.value.flatMap(t => t.pictures).filter(p => selected.value.includes(p.id)))
function goLibrary() { expanded.value = false; void router.push('/overseas/archive') }
function goStudio() { void router.push('/preview-studio-process/index.html') }
function confirmArchive() {
  if (!selectedPictures.value.length) return
  save(selectedPictures.value)
  archived.value = [...new Set([...archived.value, ...selected.value])]
  selected.value = []; confirmOpen.value = false
  ElMessage.success('预览归档成功，已记录归档人和时间，可前往成品库查看')
}
function send() { if (!running.value && (text.value.trim() || pending.value.length)) play(true) }
function onSendKey(event: Event | KeyboardEvent) { if (event instanceof KeyboardEvent) handleSendKey(event, send) }
function drop(event: DragEvent) { const id = event.dataTransfer?.getData('application/x-preview-material'); if (id) add(materials.filter(a => a.id === id)); else explain() }
</script>
