<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <ArchivePreview v-if="route.path === '/overseas/archive'" />
    <div v-show="route.path !== '/overseas/archive'" class="hx-page preview-task">
      <div class="hx-heading"><div><h1>直杆实木布罩灯-乡村风测试</h1><p>直杆实木布罩灯-乡村风 · OUTON · Amazon · 美国/英语 · 负责设计：张帅</p></div><div class="studio-actions"><ElButton size="small" @click="explain">刷新任务详情</ElButton><ElButton size="small" @click="explain">返回任务列表</ElButton></div></div>
      <div class="studio-page">
        <div class="studio-steps"><span class="done">① 运营提交图需</span><i></i><span class="done">② 设计人工审核</span><i></i><span class="active">③ AI 设计工作台</span><i></i><span>④ 归档成品库</span></div>
        <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }">
          <div class="studio-chat-heading"><strong>与 Codex 协作 <small class="preview-label">交互预览 · 示例数据</small></strong><div class="studio-actions"><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ materials.length }}</ElButton><ElButton size="small" @click="explain">刷新</ElButton><ElButton size="small" @click="explain">开始新对话</ElButton><ElButton size="small" type="primary" :disabled="!selected.length" @click="archive">归档成品（{{ selected.length }}）</ElButton><ElButton size="small" :disabled="!archived.length" @click="explain">完成任务</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton></div></div>
          <div class="studio-workspace"><section class="studio-conversation">
            <div ref="chat" class="studio-messages">
              <article v-for="turn in turns" :key="turn.id" class="studio-message" :class="turn.role">
                <div class="studio-message-name">{{ turn.role === 'user' ? '设计师' : 'Codex' }}<small v-if="turn.role === 'assistant'">示例</small></div>
                <div class="studio-bubble"><ElTag v-if="turn.role === 'user'" size="small">{{ skill }}</ElTag><p>{{ turn.text }}</p><Attachments v-if="turn.files.length" :assets="turn.files" title="消息图片" />
                  <template v-if="turn.pictures?.length"><details class="studio-execution"><summary>执行消息 · 已完成（示例）</summary><p>这里沿用当前执行消息区域，演示未调用 Codex。</p></details>
                    <div class="studio-selection-bar"><ElCheckbox :model-value="turn.pictures.every(p => selected.includes(p.id))" :indeterminate="turn.pictures.some(p => selected.includes(p.id)) && !turn.pictures.every(p => selected.includes(p.id))" @change="toggleGroup(turn.pictures)">全选本组</ElCheckbox><span>已选 {{ turn.pictures.filter(p => selected.includes(p.id)).length }} / {{ turn.pictures.length }} 张</span></div>
                    <div class="studio-pictures"><div v-for="picture in turn.pictures" :key="picture.id" class="studio-picture" :class="{ selected: selected.includes(picture.id) }"><AssetImage :asset="picture" :group="turn.pictures" title="生成图片" /><div class="studio-picture-footer"><ElCheckbox :model-value="selected.includes(picture.id)" @change="toggle(picture.id)">{{ picture.name }}</ElCheckbox><ElButton text type="primary" size="small" @click="editing = picture">修改这张</ElButton><small v-if="archived.includes(picture.id)">已归档</small></div></div></div>
                  </template>
                </div>
              </article>
            </div>
            <div class="studio-composer" @dragover.prevent @drop.prevent="drop" @paste="paste">
              <button class="studio-dropzone" :class="{ 'is-dragging': dragging }" @click="input?.click()" @dragover.prevent="dragging = true" @dragleave="dragging = false">{{ dragging ? '松开即可添加附件' : '拖拽图片或文件到这里，或点击上传' }} <small>最多 100 个附件 · 单个最大 500 MB</small></button>
              <div class="composer-files" v-if="attachments.length || revisions.length">
                <Attachments :assets="attachments" title="待发送图片" removable compact @remove="attachments = attachments.filter(a => a.id !== $event)" />
                <RevisionDraft v-for="revision in revisions" :key="revision.base.id" :revision="revision" @edit="editing = revision.base" @remove="revisions = revisions.filter(r => r.base.id !== revision.base.id)" />
              </div>
              <ElInput v-model="text" type="textarea" :rows="2" resize="none" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown.ctrl.enter.prevent="send" />
              <div class="studio-compose-tools"><div class="studio-input-tools"><ElSelect v-model="skill" aria-label="选择 Skill"><ElOption :value="'OUTON 亚马逊新品整套主图生成'" /><ElOption value="不指定 Skill" /></ElSelect><ElButton text type="primary" size="small" @click="explain">查看 Skill 说明</ElButton></div><ElButton type="primary" :disabled="!canSend" @click="send">发送</ElButton></div>
              <p class="studio-compose-note">支持 JPG/PNG/WebP、PDF/DOCX/PPTX/XLS/XLSX/CSV/TXT · Ctrl + Enter 发送 · 素材整理仅保存在本机，发送仅作演示。</p>
              <input ref="input" type="file" multiple hidden accept=".jpg,.jpeg,.png,.webp,.pdf,.docx,.pptx,.xls,.xlsx,.csv,.txt" @change="upload">
            </div>
          </section><Materials v-if="materialsOpen" :assets="materials" @close="materialsOpen = false" @add="add" @remove="removeMaterial" @duplicate="demoDuplicate" @reset="resetMaterials" /></div>
        </ElCard>
      </div>
    </div>
    <AnnotationDialog :asset="editing" :epoch="epoch" @close="editing = undefined" @confirm="confirm" />
  </OverseasShell>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import Attachments from './Attachments.vue'
import RevisionDraft from './RevisionDraft.vue'
import AssetImage from './AssetImage.vue'
import Materials from './Materials.vue'
import AnnotationDialog from './AnnotationDialog.vue'
import { usePreview } from './state'
import ArchivePreview from './ArchivePreview.vue'
const route = useRoute()
const expanded = ref(false), materialsOpen = ref(true), dragging = ref(false), input = ref<HTMLInputElement>()
const { materials, attachments, turns, text, skill, revisions, editing, epoch, selected, archived, chat, canSend, add, receive, confirm, send, toggle, toggleGroup, archive, removeMaterial, demoDuplicate, resetMaterials } = usePreview()
function explain() { ElMessage.info('独立交互预览：本轮体验图片预览、圈注回填与模拟发送，不连接真实业务。') }
function upload(event: Event) { const target = event.target as HTMLInputElement; receive(Array.from(target.files || [])); target.value = '' }
function drop(event: DragEvent) { dragging.value = false; const id = event.dataTransfer?.getData('application/x-preview-material'); if (id) add(materials.value.filter(a => a.id === id)); else receive(Array.from(event.dataTransfer?.files || [])) }
function paste(event: ClipboardEvent) { if (event.clipboardData?.files.length) { event.preventDefault(); receive(Array.from(event.clipboardData.files)) } }
</script>
