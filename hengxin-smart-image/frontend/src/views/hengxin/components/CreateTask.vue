<template>
  <div class="hx-page hx-create-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">AI IMAGE WORKSPACE</span><h1>{{ labels[mode] }}</h1><p>{{ descriptions[mode] }}</p></div><ElButton @click="router.push('/tasks/index')">查看任务 <ArtSvgIcon icon="ri:arrow-right-up-line" /></ElButton></div>
    <ElAlert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon class="hx-gap"><ElButton text @click="load">重试加载</ElButton></ElAlert>
    <ElAlert v-if="!loading && !loadError && !skill && (template || mode === 'text')" title="当前处理能力不可用，请联系超级管理员配置后再提交。" type="warning" :closable="false" show-icon class="hx-gap" />
    <div class="hx-create-grid">
      <div class="hx-stack">
        <ElCard v-if="mode !== 'text'" class="art-card hx-section hx-template-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">01</span>套图模板</h2><ElButton :disabled="submitting" @click="choosing = true">{{ template ? '更换模板' : '选择模板' }}<ArtSvgIcon icon="ri:arrow-right-s-line" /></ElButton></div>
          <template v-if="template">
            <div class="hx-selected-template"><strong>{{ template.name }}</strong><span>{{ template.images.length }} 张 · v{{ template.version }}<ElTag size="small" type="success">当前使用</ElTag></span></div>
            <div class="hx-template-filmstrip"><div v-for="(picture, index) in template.images.slice(0, 6)" :key="index" class="hx-template-frame"><PicturePreview :picture="picture" :pictures="template.images" :index="index" :title="template.name" /><span v-if="index === 5 && template.images.length > 6" class="hx-template-remaining">另 {{ template.images.length - 6 }} 张</span></div></div>
            <p class="hx-preview-hint">点击图片放大 · 左右查看整套</p>
          </template>
          <ElEmpty v-else :description="loading ? '正在加载模板…' : '选择一套模板，开始制作'" :image-size="48" />
        </ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">{{ mode === 'text' ? '01' : '02' }}</span>{{ mode === 'text' ? '上传待修改图片' : '上传替换素材' }}</h2></div>
          <ImageUpload v-model="sources" :mode="mode" :disabled="submitting" @blocked="uploadBlocked = $event" @example="example" />
        </ElCard>

      </div>
      <aside class="hx-summary">
        <ElCard class="art-card hx-section hx-task-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">{{ mode === 'text' ? '02' : '03' }}</span>任务信息</h2><span class="hx-muted">方便后续查找与归档</span></div>
          <ElForm class="hx-task-form" label-position="top" :disabled="submitting">
            <ElFormItem label="任务名称" required><ElInput v-model="name" aria-label="任务名称" placeholder="例如：秋日上新 · 手机屏幕套图" maxlength="60" show-word-limit /></ElFormItem>
            <ElFormItem label="SKU（选填）"><ElInput v-model="sku" aria-label="SKU" placeholder="填写商品 SKU，便于识别" maxlength="80" show-word-limit /></ElFormItem>
            <ElFormItem :label="mode === 'text' ? '文字修改要求' : '补充说明（选填）'" :required="mode === 'text'"><ElInput v-model="note" aria-label="修改要求" type="textarea" :rows="2" :placeholder="mode === 'text' ? '例如：将「夏日特惠」改为「秋日上新」，其余内容保持不变' : '告诉我们这次需要特别注意的地方'" maxlength="1000" show-word-limit /></ElFormItem>
          </ElForm>
        </ElCard>
        <ElCard class="art-card hx-summary-card" shadow="never">
          <ElButton type="primary" size="large" class="hx-full hx-gap" :loading="submitting" :disabled="blocked || !!accepted" @click="submit()"><ArtSvgIcon icon="ri:sparkling-line" /> 提交生成任务</ElButton>
          <ElAlert v-if="!accepted && !loading && !loadError && validationErrors.length" title="提交前还需要完成" type="info" :closable="false" class="hx-gap"><div class="hx-checklist"><span v-for="item in validationErrors" :key="item">{{ item }}</span></div></ElAlert>
          <dl><div><dt>处理类型</dt><dd>{{ labels[mode] }}</dd></div><div><dt>已选模板</dt><dd>{{ mode === 'text' ? '无需模板' : template ? `${template.name} · v${template.version}` : '尚未选择' }}</dd></div><div><dt>替换素材</dt><dd>{{ sources.length }} 张</dd></div><div><dt>预计输出</dt><dd>{{ mode === 'text' ? sources.length : template?.images.length || 0 }} 张</dd></div></dl>
          <div class="hx-skill-note"><ArtSvgIcon icon="ri:sparkling-2-line" /><div><strong>{{ loading ? '加载 Skill…' : skill?.name || '暂无可用 Skill' }}</strong><small>{{ skill ? (isMockMode ? '模拟绑定' : '使用最近同步成功的内容') : '请联系超级管理员配置可用 Skill' }}</small></div></div>
          <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon class="hx-gap" />
          <ElAlert v-if="accepted" :title="`任务已受理：${accepted.taskId}`" type="success" :closable="false" class="hx-gap"><ElButton text @click="viewAccepted">查看已受理任务</ElButton><ElButton text @click="startNew">另建任务</ElButton></ElAlert>
          <ElAlert v-else-if="uncertain" title="上次提交结果尚未确认；输入已保留，请确认原请求以避免重复任务。" type="warning" :closable="false" class="hx-gap"><ElButton text :loading="submitting" @click="submit(true)">确认上次提交</ElButton></ElAlert>


          <p v-if="uploadBlocked" class="hx-footnote">请等待图片接收完成；失败图片需重试或移除。</p>
          <p class="hx-footnote">{{ isMockMode ? '生成返回示例图片，仅用于前端预览。' : '任务受理后可在任务中心查看状态。' }}</p>
        </ElCard>

      </aside>
    </div>
    <TemplatePicker v-model="choosing" v-model:search="search" v-model:page="page" :templates="available" :selected-id="template?.id" :total="total" :page-size="pageSize" :loading="loading" :error="loadError" :disabled="submitting" @select="select($event); choosing = false" @retry="load" />
  </div>
</template>
<script setup lang="ts">
import { ref, toRef } from 'vue'
import { useRouter } from 'vue-router'
import { isMockMode } from '@/api/hengxin/client'
import { labels, type Mode } from '../model'
import { useCreateTask } from '../use-create-task'
import ImageUpload from './ImageUpload.vue'
import PicturePreview from './PicturePreview.vue'
import TemplatePicker from './TemplatePicker.vue'
const choosing = ref(false)
const props = defineProps<{ mode: Mode }>()
const router = useRouter()
const descriptions = { wallpaper: '保留商品与画面设计，为整套图片换上新的屏幕壁纸。', product: '复用成熟的商品模板，让新商品自然融入原有场景。', text: '说清楚要改的文字，其余处理交给对应的 Skill。' }
const { available, template, sources, name, sku, note, search, page, pageSize, total, loading, loadError, error,
  submitting, uploadBlocked, skill, blocked, validationErrors, select, load, example, submit, accepted, uncertain, viewAccepted, startNew } = useCreateTask(toRef(props, 'mode'))
</script>

<style scoped>
.hx-selected-template { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.hx-selected-template strong { font-size:15px; overflow-wrap:anywhere; }
.hx-selected-template>span { display:flex; align-items:center; gap:12px; white-space:nowrap; font-size:12px; color:var(--art-gray-600); }
.hx-template-filmstrip { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:8px; }
.hx-template-frame { position:relative; min-width:0; height:112px; }
.hx-template-remaining { position:absolute; right:4px; bottom:4px; padding:2px 6px; background:rgb(20 28 42 / 78%); color:white; border-radius:4px; font-size:11px; pointer-events:none; }
.hx-preview-hint { margin:8px 0 0; color:var(--art-gray-600); font-size:12px; }
.hx-checklist { display:flex; flex-wrap:wrap; gap:6px 16px; color:var(--art-gray-700); font-size:12px; }
.hx-checklist span::before { content:'·'; color:var(--el-color-primary); margin-right:4px; }

.hx-create-page { padding-top:8px; max-width:1480px; margin-inline:auto; }
.hx-create-page .hx-heading { margin-bottom:14px; }
.hx-create-page .hx-eyebrow { display:none; }
.hx-create-page .hx-heading h1 { font-size:22px; margin:0 0 4px; }
.hx-create-page .hx-heading p { margin:0; }
.hx-create-grid { grid-template-columns:minmax(0,1fr) 380px; gap:16px; }
.hx-stack { gap:16px; }
.hx-template-section,.hx-task-section { min-height:256px; }
.hx-create-page :deep(.el-card__body) { padding:16px; }
.hx-create-page .hx-section-title { margin-bottom:12px; }
.hx-selected-template .hx-muted { margin:4px 0; font-size:12px; }
.hx-summary { top:110px; display:grid; gap:16px; }
.hx-task-form { display:grid; grid-template-columns:1fr 1fr; gap:0 12px; }
.hx-task-form :deep(.el-form-item) { margin-bottom:12px; min-width:0; }
.hx-task-form :deep(.el-form-item:last-child) { grid-column:1/-1; margin-bottom:0; }
.hx-task-form :deep(.el-form-item__label) { margin-bottom:5px; }
.hx-summary dl { margin:10px 0 8px; display:grid; grid-template-columns:1fr 1fr; gap:0 12px; }
.hx-summary dl>div:nth-child(2) { grid-column:1/-1; grid-row:2; }
.hx-summary dl>div { padding:2px 0; }
.hx-skill-note { padding:6px 8px; margin-bottom:6px; }
.hx-skill-note>div { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.hx-skill-note small { margin:0; }
.hx-summary-card :deep(.el-button.hx-full) { margin-top:0; }
.hx-summary .hx-gap { margin-top:10px; }
.hx-summary .hx-footnote { margin:6px 0 0; }
.hx-create-page :deep(.el-upload-dragger) { padding:12px 16px; }
.hx-create-page :deep(.hx-upload-icon) { width:32px; height:32px; font-size:20px; margin-bottom:6px; }
.hx-create-page :deep(.hx-footnote) { margin-top:6px; }
@media(max-width:1100px) { .hx-create-grid { grid-template-columns:minmax(0,1fr) 340px; } }
@media(max-width:900px) { .hx-create-grid { grid-template-columns:1fr; } .hx-summary { position:static; } }
@media(max-width:1100px) { .hx-template-frame { height:100px; } }
@media(max-width:600px) { .hx-template-filmstrip { grid-template-columns:repeat(3,minmax(0,1fr)); } .hx-selected-template { align-items:flex-start; flex-direction:column; gap:6px; } }
@media(max-width:480px) { .hx-task-form { grid-template-columns:1fr; } }
</style>
