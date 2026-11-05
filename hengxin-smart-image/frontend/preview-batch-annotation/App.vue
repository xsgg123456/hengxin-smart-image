<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="hx-page preview-task studio-page">
      <div class="hx-heading"><div><h1>WAIFAIR IT通用测试-1104-张帅</h1><p>WAIFAIR IT通用测试-1104-张帅 · OUTON · Wayfair · 语言：英语 · 负责设计：张帅</p></div><div class="studio-actions"><ElButton size="small" @click="explain">刷新任务详情</ElButton><ElButton size="small" @click="explain">返回任务列表</ElButton></div></div>
      <div class="batch-preview-banner"><span>{{ baseline ? '原组件对照' : '独立交互预览' }} · 示例图片 · 文件仅本地读取 · 不调用AI · 刷新重置</span><a :href="baseline ? './index.html' : './index.html?baseline=1'">{{ baseline ? '查看新交互' : '查看原界面对照' }}</a></div>
      <div class="studio-steps"><span class="done">① 提交图需</span><i /><span class="done">② 图需审核</span><i /><span class="active">③ AI 设计工作台</span><i /><span>④ 归档成品库</span></div>
      <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }">
        <div class="studio-chat-heading"><strong>与 Codex 协作</strong><div class="studio-actions"><ElButton size="small" @click="sessionsOpen = !sessionsOpen">会话 · 5/10</ElButton><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ taskMaterials.length }}</ElButton><ElButton size="small" @click="explain">刷新</ElButton><ElButton size="small" disabled>查看本任务成品</ElButton><ElButton size="small" disabled>完成任务</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton></div></div>
        <div class="studio-workspace">
          <StudioSessionList v-if="sessionsOpen" :sessions="sessions" active-id="session-3" :disabled="false" :can-create="true" @select="explain" @create="explain" @action="explain" @close="sessionsOpen = false" />
          <section class="studio-conversation">
            <div class="session-current"><div><strong>茶几灯-主图和A+</strong><small>当前会话 · 上下文与工作文件独立</small></div><div><ElButton size="small" @click="explain">取回文件</ElButton><ElButton text size="small" @click="explain">重命名</ElButton></div></div>
            <PreviewTurns :turns="turns" :transcript="[]" conversation-id="session-3" :selected="selectedPictures" :disabled="false" :baseline="baseline" @modify="openSingle" @batch="openBatch" @toggle="toggle" @group="group" @failure="failure">
              <template #sent-materials="{ turnId }"><ElButton v-if="sentMaterials[turnId]?.length" text type="primary" size="small" @click="detailItems = sentMaterials[turnId]">查看本轮修改材料（{{ sentMaterials[turnId].length }}张）</ElButton></template>
            </PreviewTurns>
            <div class="studio-selection-bar selection-footer"><span>已选当前会话 {{ selectedPictures.length }} 张图片</span><ElButton size="small" :disabled="!selectedPictures.length" @click="explain">下载所选图片（{{ selectedPictures.length }}）</ElButton><ElButton size="small" type="primary" :disabled="!selectedPictures.length" @click="explain">归档所选图片（{{ selectedPictures.length }}）</ElButton></div>
            <div class="studio-composer">
              <div v-if="revisions.length" class="batch-revision-list" aria-label="待发送修改">
                <article v-for="r in revisions" :key="r.picture.id" class="revision-draft">
                  <div class="revision-thumbs"><ElImage :src="r.picture.url" :alt="r.picture.name" fit="contain" :preview-src-list="[r.picture.url]" preview-teleported :z-index="6500" /></div>
                  <div class="revision-summary"><strong>修改 {{ r.picture.name }}</strong><small>标注{{ r.marks.length }}处 · 参考图{{ r.references.length }}张 · 待发送</small></div>
                  <div class="revision-actions"><ElButton text size="small" type="primary" @click="detailItems = [r]">查看修改材料</ElButton><ElButton text size="small" type="primary" @click="openSingle(r.picture)">继续编辑</ElButton><ElButton text size="small" :aria-label="`取消修改 ${r.picture.name}`" @click="revisions = revisions.filter(x => x.picture.id !== r.picture.id)">×</ElButton></div>
                </article>
              </div>
              <button class="studio-dropzone" @click="explain">拖拽图片或文件到这里，或点击上传 <small>仅加入当前会话 · 最多100个附件 · 单个最大500 MB</small></button>
              <p v-if="sendError" role="alert" class="reference-error">{{ sendError }}</p>
              <ElInput v-model="text" type="textarea" :rows="2" resize="none" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown="keySend" />
              <div class="studio-compose-tools"><ElSelect v-model="skill" aria-label="选择 Skill" placeholder="选择 Skill（可选）" clearable><ElOption label="OUTON 灯具家居套图" value="outon" /></ElSelect><div class="studio-send-tools"><ElButton text @click="textExpanded = true">展开编辑</ElButton><ElButton type="primary" :disabled="!text.trim() && !revisions.length" @click="previewSend">发送</ElButton></div></div>
              <p class="studio-compose-note">发送到：茶几灯-主图和A+ · Enter 发送，Shift + Enter 换行 · 本页草稿自动保留</p>
            </div>
          </section>
          <StudioMaterials v-if="materialsOpen" :assets="taskMaterials" :disabled="false" @close="materialsOpen = false" @add="explain" @remove="explain" @remove-selected="explain" @failure="failure" />
        </div>
      </ElCard>
    </div>
    <EditorDialog v-if="editing && !baseline" :key="editing.key" :pictures="editing.pictures" :initial-id="editing.id" :batch="editing.batch" @close="editing = undefined" @confirm="receive" />
    <StudioAnnotationDialog v-if="baselinePicture" :picture="baselinePicture" :draft-key="`preview-baseline:${baselinePicture.id}`" :submitting="false" error="" @close="baselinePicture = undefined" @confirm="baselineConfirm" @failure="failure" />
    <ElDialog :model-value="!!detailItems" title="本次修改材料" width="min(980px,94vw)" align-center append-to-body class="batch-review-dialog" @update:model-value="!$event && (detailItems = undefined)"><RevisionDetails v-if="detailItems" :items="detailItems" /><template #footer><ElButton @click="detailItems = undefined">关闭</ElButton></template></ElDialog>
    <ElDialog v-model="sendOpen" title="本次发送预览" width="min(980px,94vw)" align-center append-to-body class="batch-review-dialog"><ElAlert title="仅模拟发送，核对下面的实际修改材料；不调用AI、不生成新图。" type="info" :closable="false" /><RevisionDetails :items="sendItems" /><p class="revision-description">{{ sendText ? `整体补充要求：\n${sendText}` : '无整体补充要求' }}</p><template #footer><ElButton @click="sendOpen = false">返回工作台</ElButton><ElButton type="primary" @click="send">确认模拟发送</ElButton></template></ElDialog>
    <ElDialog v-model="textExpanded" title="编辑修改要求" width="min(760px,94vw)" append-to-body><ElInput v-model="text" type="textarea" :rows="10" aria-label="展开的设计要求" /><template #footer><ElButton type="primary" @click="textExpanded = false">完成编辑</ElButton></template></ElDialog>
  </OverseasShell>
</template>
<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { StudioPicture, StudioTurn } from '@/api/overseas/studio'
import type { PreparedAnnotation } from '@/views/hengxin/components/annotation/AnnotationEditor.vue'
import { cloneMarks } from '@/views/hengxin/components/annotation/annotation-model'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import StudioSessionList from '@/views/overseas/studio/StudioSessionList.vue'
import StudioMaterials from '@/views/overseas/studio/StudioMaterials.vue'
import StudioAnnotationDialog from '@/views/overseas/studio/StudioAnnotationDialog.vue'
import PreviewTurns from './PreviewTurns.vue'
import EditorDialog from './EditorDialog.vue'
import RevisionDetails from './RevisionDetails.vue'
import { commitRevisions, disposeUrls, materials, objectUrls, pictures, referenceLabel, revisions, seedTurn, sessions, type Revision } from './state'
const baseline = new URLSearchParams(location.search).get('baseline') === '1'
const text = ref(''), skill = ref(''), sessionsOpen = ref(true), materialsOpen = ref(true), expanded = ref(false), textExpanded = ref(false)
const taskMaterials = ref(materials), turns = ref<StudioTurn[]>([seedTurn]), selectedPictures = ref<string[]>([])
const editing = ref<{ key: string; pictures: StudioPicture[]; id: string; batch: boolean }>(), baselinePicture = ref<StudioPicture>()
const detailItems = ref<Revision[]>(), sendOpen = ref(false), sendItems = ref<Revision[]>([]), sendText = ref(''), sendError = ref('')
const sentMaterials = ref<Record<string, Revision[]>>({})
function explain() { ElMessage.info('本预览聚焦批量标注和单图参考，其他业务操作请在正式系统使用。') }
function failure(reason: unknown) { ElMessage.error(reason instanceof Error ? reason.message : '图片读取失败，请重试') }
function openSingle(p: StudioPicture) { if (baseline) { baselinePicture.value = p; return }; editing.value = { key: crypto.randomUUID(), pictures: [p], id: p.id, batch: false } }
function openBatch(group: StudioPicture[]) { editing.value = { key: crypto.randomUUID(), pictures: group, id: group[0].id, batch: true } }
function receive(items: Revision[], groupIds?: string[]) { if (groupIds) revisions.value = revisions.value.filter(r => !groupIds.includes(r.picture.id)); commitRevisions(items); editing.value = undefined; sendError.value = ''; ElMessage.success(`已带回${items.length}张图片，补充后点击发送`) }
function baselineConfirm(value: PreparedAnnotation) { const p = baselinePicture.value; if (!p) return; const annotation = value.file ? URL.createObjectURL(value.file) : ''; if (annotation) objectUrls.add(annotation); commitRevisions([{ picture: p, marks: [], references: [], annotation, text: value.text }]); baselinePicture.value = undefined }
function toggle(id: string) { selectedPictures.value = selectedPictures.value.includes(id) ? selectedPictures.value.filter(p => p !== id) : [...selectedPictures.value, id] }
function group(items: StudioPicture[]) { const ids = items.map(p => p.id); selectedPictures.value = ids.every(id => selectedPictures.value.includes(id)) ? selectedPictures.value.filter(id => !ids.includes(id)) : [...new Set([...selectedPictures.value, ...ids])] }
function previewSend() {
  sendError.value = ''
  if (!text.value.trim() && !revisions.value.length) return
  if (revisions.value.some(r => !r.text.trim()) && !text.value.trim()) { sendError.value = '有图片尚未填写修改意见，请在输入区补充要求。'; return }
  sendItems.value = revisions.value.map(r => ({ ...r, picture: { ...r.picture }, marks: cloneMarks(r.marks), references: r.references.map(x => ({ ...x })) })); sendText.value = text.value; sendOpen.value = true
}
function keySend(e: Event | KeyboardEvent) { if (e instanceof KeyboardEvent && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); previewSend() } }
function send() {
  const summary = sendItems.value.map(r => `修改${r.picture.name}：\n${r.text}\n${r.references.map((x, i) => `参考图${i + 1}（${referenceLabel(x.kind, x.customPurpose)}，${x.name}）：${x.note}`).join('\n')}`).join('\n\n')
  const id = crypto.randomUUID()
  sentMaterials.value[id] = sendItems.value
  turns.value.push({ ...seedTurn, id, pictures: [], createdAt: new Date().toISOString(), text: [summary, sendText.value].filter(Boolean).join('\n\n'), reply: `已模拟发送${sendItems.value.length}张图片的修改材料。本预览未调用AI，也未生成新图；原六张图片保留。` })
  revisions.value = []; text.value = ''; sendOpen.value = false; ElMessage.success('模拟发送完成，原图片未改动')
}
onUnmounted(disposeUrls)
</script>
