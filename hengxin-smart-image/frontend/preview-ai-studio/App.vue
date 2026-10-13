<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="hx-page studio-page">
      <div class="studio-preview">交互预览 · 未连接 Codex，附件仅在本地浏览器读取，刷新后重置</div>
      <template v-if="route.path === '/overseas/tasks'">
        <div class="hx-heading"><div><h1>AI 设计工作台</h1><p>OUTON 置物架落地灯 · Amazon 美国站 · SKU Z22-07</p></div><div class="studio-actions"><ElButton type="primary" :disabled="!selected.length || busy" @click="archiveOpen = true">归档成品{{ selected.length ? `（${selected.length}）` : '' }}</ElButton></div></div>
        <div class="studio-steps"><span class="done">① 运营提交图需</span><i></i><span class="done">② 设计人工审核</span><i></i><span class="active">③ AI 设计工作台</span><i></i><span :class="{ done: archived.length }">④ 归档成品库</span></div>
        <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }" @keydown.esc="expanded = false">
          <div class="studio-chat-heading"><strong>与 Codex 协作</strong><div><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ taskMaterials.length }}</ElButton><ElButton text size="small" @click="example" :disabled="busy">查看示例对话</ElButton><ElButton text size="small" @click="clear">清空对话</ElButton><ElButton v-if="expanded" text type="primary" :disabled="!selected.length || busy" @click="archiveOpen = true">归档成品（{{ selected.length }}）</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton></div></div>
          <div class="studio-workspace"><section class="studio-conversation">
          <div ref="chat" class="studio-messages" aria-live="polite">
            <div v-if="!messages.length" class="studio-empty"><div class="studio-mark"><ChatDotRound /></div><h2>从你的设计需求开始</h2><p>选择一个 Skill，添加产品图片或需求文件，直接告诉 Codex 你想怎么做。</p><div class="studio-hints"><span>上传产品素材</span><span>按需选择 Skill</span><span>随时继续修改</span></div></div>
            <article v-for="message in messages" :key="message.id" :class="['studio-message', message.role]">
              <div class="studio-message-name">{{ message.role === 'user' ? '设计师' : 'Codex' }}<small v-if="message.role === 'assistant'">模拟</small></div>
              <div class="studio-bubble"><ElTag v-if="message.skill" size="small" class="studio-skill-label">{{ message.skill }}</ElTag><p>{{ message.text }}</p>
                <div v-if="message.files?.length" class="studio-attachments"><div v-for="file in message.files" :key="file.id" class="studio-attachment"><ElImage v-if="file.image" :src="file.url" :preview-src-list="[file.url]" preview-teleported fit="cover" /><a v-else :href="file.url" :download="file.name">{{ file.name }}</a><span v-if="file.image">{{ file.name }}</span></div></div>
                <div v-if="message.pictures?.length" class="studio-selection-bar"><ElCheckbox :model-value="message.pictures.every(url => selected.includes(url))" :indeterminate="message.pictures.some(url => selected.includes(url)) && !message.pictures.every(url => selected.includes(url))" @change="toggleGroup(message.pictures)">{{ message.pictures.every(url => selected.includes(url)) ? '取消全选' : '全选本组' }}</ElCheckbox><span>已选 {{ message.pictures.filter(url => selected.includes(url)).length }} / {{ message.pictures.length }} 张</span></div><div v-if="message.pictures" class="studio-pictures"><div v-for="(url, index) in message.pictures" :key="url" class="studio-picture" :class="{ selected: selected.includes(url) }"><ElImage :src="url" :preview-src-list="message.pictures" :initial-index="index" preview-teleported fit="contain" /><div class="studio-picture-footer"><ElCheckbox :model-value="selected.includes(url)" @change="toggle(url)">图片 {{ index + 1 }}</ElCheckbox><ElButton text type="primary" size="small" @click="modify(url)">修改这张</ElButton></div></div></div>
              </div>
            </article>
            <div v-if="busy" class="studio-working"><ElIcon class="is-loading"><Loading /></ElIcon>正在演示回复…</div>
          </div>
          <div class="studio-composer" @dragover.prevent @drop.prevent="dropFiles" @paste="paste">
            <button type="button" class="studio-dropzone" :class="{ 'is-dragging': dragging }" @dragover.prevent.stop="dragging = true" @dragleave.prevent="dragging = false" @click="mixedInput?.click()"><Paperclip /><span>{{ dragging ? '松开即可添加图片或文件' : '拖拽图片或文件到这里，或点击上传' }}</span><small>支持多文件 · 单个最大 20 MB</small></button>
            <div v-if="reference" class="studio-reference"><img :src="reference" alt="本轮修改参考"><span>正在修改图片 {{ imageNumber(reference) }}</span><ElButton text size="small" @click="reference = ''">取消引用</ElButton></div>
            <div v-if="attachments.length" class="studio-attachments pending"><div v-for="file in attachments" :key="file.id" class="studio-attachment"><ElImage v-if="file.image" :src="file.url" :preview-src-list="[file.url]" preview-teleported fit="cover" /><Document v-else class="studio-file-icon" /><span :title="file.name">{{ file.name }}</span><ElButton text :aria-label="`移除 ${file.name}`" @click="removeAttachment(file.id)">×</ElButton></div></div>
            <ElInput v-model="text" type="textarea" :rows="2" resize="none" aria-label="设计要求" placeholder="描述你的设计要求，或继续提出修改意见…" @keydown.ctrl.enter.prevent="send" />
            <div class="studio-compose-tools"><div class="studio-input-tools"><ElSelect v-model="skill" placeholder="选择 Skill（可选）" clearable filterable aria-label="选择 Skill"><ElOption v-for="item in skills" :key="item" :value="item" :label="item" /></ElSelect></div><ElButton v-if="busy" @click="stop">停止</ElButton><ElButton v-else type="primary" :disabled="!canSend" @click="send" :icon="Top">发送</ElButton></div>
            <div class="studio-compose-note">支持拖拽文件、粘贴图片 · 单个文件最大 20 MB · Ctrl + Enter 发送</div>
            <input ref="mixedInput" type="file" accept="image/png,image/jpeg,image/webp,.pdf,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.csv,.txt" multiple hidden @change="upload">
          </div>
          </section><TaskMaterials v-if="materialsOpen" @close="materialsOpen = false" @add="addMaterials" /></div>
        </ElCard>
      </template>
      <template v-else-if="route.path === '/overseas/archive'">
        <div class="hx-heading"><div><h1>成品库</h1><p>本次预览中已归档的图片。</p></div><ElButton @click="router.push('/overseas/tasks')">返回工作台</ElButton></div>
        <ElCard class="art-card" shadow="never"><ElEmpty v-if="!archived.length" description="暂无归档图片，请在工作台勾选满意的图片后归档" /><div v-else class="studio-archive-grid"><div v-for="(url, index) in archived" :key="url" class="studio-picture"><ElImage :src="url" :preview-src-list="archived" :initial-index="index" preview-teleported fit="contain" /><div class="studio-picture-footer"><span>OUTON · 图片 {{ imageNumber(url) }}</span><ElButton text type="danger" @click="removeArchive(url)">移除</ElButton></div></div></div></ElCard>
      </template>
      <ElResult v-else title="本次预览聚焦 AI 设计工作台" sub-title="其他业务页面继续沿用现有系统，本预览不连接真实业务。"><template #extra><ElButton type="primary" @click="router.push('/overseas/tasks')">进入工作台</ElButton></template></ElResult>
    </div>
    <ElDialog v-model="archiveOpen" title="归档成品" width="min(620px, 94vw)"><p>将所选 {{ selected.length }} 张图片归档到此任务，归档后可在成品库查看。</p><div class="studio-archive-thumbs"><img v-for="url in selected" :key="url" :src="url" alt="待归档示例图片"></div><p class="hx-muted">交互预览，仅保存在当前页面，刷新后重置。</p><template #footer><ElButton @click="archiveOpen = false">取消</ElButton><ElButton type="primary" :disabled="!selected.length || busy" @click="archive">确认归档</ElButton></template></ElDialog>
  </OverseasShell>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Document, Loading, Paperclip, Top } from '@element-plus/icons-vue'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import TaskMaterials from './TaskMaterials.vue'
import { useStudio, skills, imageNumber, taskMaterials } from './state'
const route = useRoute(), router = useRouter()
const expanded = ref(false)
const dragging = ref(false), mixedInput = ref<HTMLInputElement>()
function dropFiles(event: DragEvent) {
  dragging.value = false
  const key = event.dataTransfer?.getData('application/x-studio-material')
  if (key) addMaterials([key])
  else receive(Array.from(event.dataTransfer?.files || []))
}
const { text, skill, busy, messages, attachments, selected, archived, chat, reference, archiveOpen, materialsOpen, allFiles, canSend, addMaterials, upload, receive, paste, removeAttachment, send, stop, modify, toggle, toggleGroup, archive, removeArchive, clear, example } = useStudio()
function explain() { ElMessage.info('本次为独立交互预览，不连接真实账号或业务') }
</script>
