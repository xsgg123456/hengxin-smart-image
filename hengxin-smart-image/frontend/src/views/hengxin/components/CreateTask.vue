<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">AI IMAGE WORKSPACE</span><h1>{{ labels[mode] }}</h1><p>{{ descriptions[mode] }}</p></div><ElButton @click="router.push('/tasks/index')">查看任务 <ArtSvgIcon icon="ri:arrow-right-up-line" /></ElButton></div>
    <ElAlert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon class="hx-gap"><ElButton text @click="load">重试加载</ElButton></ElAlert>
    <ElAlert v-if="!loading && !loadError && !skill && (template || mode === 'text')" title="当前处理能力不可用，请联系超级管理员配置后再提交。" type="warning" :closable="false" show-icon class="hx-gap" />
    <div class="hx-create-grid">
      <div class="hx-stack">
        <ElCard v-if="mode !== 'text'" class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">01</span>选择套图模板</h2><ElButton text type="primary" @click="router.push('/templates/index')">管理模板 <ArtSvgIcon icon="ri:arrow-right-line" /></ElButton></div>
          <div v-if="template && !choosing" class="hx-selected-template">
            <PicturePreview :picture="template.images[0]!" :pictures="template.images" :title="template.name" />
            <div><strong>{{ template.name }}</strong><p class="hx-muted">{{ template.images.length }} 张 · v{{ template.version }} · 点击缩略图查看整套</p><ElTag size="small" type="success">已选择</ElTag></div>
            <ElButton :disabled="submitting" @click="choosing = true">更换模板</ElButton>
          </div>
          <template v-else>
            <div v-if="template" class="hx-picker-heading"><span>选择新的模板，或保留当前模板</span><ElButton text :disabled="submitting" @click="choosing = false">取消更换</ElButton></div>
            <ElInput v-model="search" placeholder="搜索可用模板" aria-label="搜索可用模板" clearable :disabled="submitting" />
            <div v-loading="loading" class="hx-template-options hx-gap">
              <div v-for="t in available" :key="t.id" class="hx-template-option" :class="{ selected: template?.id === t.id }">
                <PictureMosaic :pictures="t.images" :title="t.name" />
                <div class="hx-picker-footer"><strong>{{ t.name }}</strong><small>v{{ t.version }}</small><div v-if="template?.id === t.id" class="hx-picker-current" role="status">✓ 当前使用</div><ElButton v-else class="hx-picker-action" :disabled="submitting || loading" @click="select(t); choosing = false">使用此模板</ElButton></div>
              </div>
            </div>
            <ElEmpty v-if="!available.length" :description="loading ? '正在加载模板…' : loadError ? '模板加载失败，请重试' : '暂无匹配模板，请清除搜索或先创建模板'" :image-size="75" />
            <ElPagination v-model:current-page="page" class="hx-gap" :page-size="pageSize" :total="total" :disabled="loading || submitting" layout="prev, pager, next, total" />
          </template>
        </ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">{{ mode === 'text' ? '01' : '02' }}</span>{{ mode === 'text' ? '上传待修改图片' : '上传替换素材' }}</h2></div>
          <ImageUpload v-model="sources" :mode="mode" :disabled="submitting" @blocked="uploadBlocked = $event" @example="example" />
        </ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">{{ mode === 'text' ? '02' : '03' }}</span>任务信息</h2><span class="hx-muted">方便后续查找与归档</span></div>
          <ElForm label-position="top" :disabled="submitting">
            <ElFormItem label="任务名称" required><ElInput v-model="name" aria-label="任务名称" placeholder="例如：秋日上新 · 手机屏幕套图" maxlength="60" show-word-limit /></ElFormItem>
            <ElFormItem label="SKU（选填）"><ElInput v-model="sku" aria-label="SKU" placeholder="填写商品 SKU，便于识别" maxlength="80" show-word-limit /></ElFormItem>
            <ElFormItem :label="mode === 'text' ? '文字修改要求' : '补充说明（选填）'" :required="mode === 'text'"><ElInput v-model="note" aria-label="修改要求" type="textarea" :rows="3" :placeholder="mode === 'text' ? '例如：将「夏日特惠」改为「秋日上新」，其余内容保持不变' : '告诉我们这次需要特别注意的地方'" maxlength="1000" show-word-limit /></ElFormItem>
          </ElForm>
        </ElCard>
      </div>
      <aside class="hx-summary">
        <ElCard class="art-card hx-summary-card" shadow="never"><div class="hx-section-title"><h2>本次任务</h2><ElTag effect="light" round>新任务</ElTag></div>
          <div v-if="template?.images[0] || sources[0]" class="hx-summary-art"><PicturePreview :picture="(template?.images[0] || sources[0])!" :pictures="template?.images || sources" :title="template ? '模板参考图' : '输入素材'" /><span>{{ template ? '模板参考图' : '输入素材预览' }}</span></div>
          <ElEmpty v-else description="添加素材后预览" :image-size="75" />
          <dl><div><dt>处理类型</dt><dd>{{ labels[mode] }}</dd></div><div><dt>已选模板</dt><dd>{{ mode === 'text' ? '无需模板' : template ? `${template.name} · v${template.version}` : '尚未选择' }}</dd></div><div><dt>替换素材</dt><dd>{{ sources.length }} 张</dd></div><div><dt>预计输出</dt><dd>{{ mode === 'text' ? sources.length : template?.images.length || 0 }} 张</dd></div></dl>
          <div class="hx-skill-note"><ArtSvgIcon icon="ri:sparkling-2-line" /><div><strong>{{ loading ? '加载 Skill…' : skill?.name || '暂无可用 Skill' }}</strong><small>{{ skill ? (isMockMode ? '模拟绑定' : '使用最近同步成功的内容') : '请联系超级管理员配置可用 Skill' }}</small></div></div>
          <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon class="hx-gap" />
          <ElAlert v-if="accepted" :title="`任务已受理：${accepted.taskId}`" type="success" :closable="false" class="hx-gap"><ElButton text @click="viewAccepted">查看已受理任务</ElButton><ElButton text @click="startNew">另建任务</ElButton></ElAlert>
          <ElAlert v-else-if="uncertain" title="上次提交结果尚未确认；输入已保留，请确认原请求以避免重复任务。" type="warning" :closable="false" class="hx-gap"><ElButton text :loading="submitting" @click="submit(true)">确认上次提交</ElButton></ElAlert>
          <ElAlert v-if="!accepted && !loading && !loadError && validationErrors.length" title="提交前还需要完成" type="info" :closable="false" class="hx-gap"><div class="hx-checklist"><span v-for="item in validationErrors" :key="item">{{ item }}</span></div></ElAlert>
          <ElButton type="primary" size="large" class="hx-full hx-gap" :loading="submitting" :disabled="blocked || !!accepted" @click="submit()"><ArtSvgIcon icon="ri:sparkling-line" /> 提交生成任务</ElButton>
          <p v-if="uploadBlocked" class="hx-footnote">请等待图片接收完成；失败图片需重试或移除。</p>
          <p class="hx-footnote">{{ isMockMode ? '生成返回示例图片，仅用于前端预览。' : '任务受理后可在任务中心查看状态。' }}</p>
        </ElCard>
        <div class="hx-tips"><h3>{{ isMockMode ? '每一次套图，都可以继续完善' : '任务进度随时可查' }}</h3><p>{{ isMockMode ? '生成后支持整套或单张提出修改意见，满意后再归档到成品库。' : '受理后可关闭页面，稍后到任务中心查看状态和结果。支持整套或单张提出修改意见，完成后可下载并归档到成品库。' }}</p></div>
      </aside>
    </div>
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
import PictureMosaic from './PictureMosaic.vue'
const choosing = ref(false)
const props = defineProps<{ mode: Mode }>()
const router = useRouter()
const descriptions = { wallpaper: '保留商品与画面设计，为整套图片换上新的屏幕壁纸。', product: '复用成熟的商品模板，让新商品自然融入原有场景。', text: '说清楚要改的文字，其余处理交给对应的 Skill。' }
const { available, template, sources, name, sku, note, search, page, pageSize, total, loading, loadError, error,
  submitting, uploadBlocked, skill, blocked, validationErrors, select, load, example, submit, accepted, uncertain, viewAccepted, startNew } = useCreateTask(toRef(props, 'mode'))
</script>

<style scoped>
.hx-picker-heading { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px; color:var(--art-gray-600); font-size:12px; }
.hx-template-option { cursor:default; display:flex; flex-direction:column; }
.hx-picker-footer { display:flex; flex-direction:column; gap:8px; padding:14px; flex:1; }
.hx-picker-footer strong { font-size:14px; overflow-wrap:anywhere; }
.hx-picker-footer small { color:var(--art-gray-600); margin-bottom:4px; }
.hx-picker-action, .hx-picker-current { width:100%; min-height:36px; margin-top:auto; box-sizing:border-box; }
.hx-picker-current { display:flex; align-items:center; justify-content:center; color:var(--el-color-primary); background:var(--el-color-primary-light-9); border-radius:var(--el-border-radius-base); font-size:14px; }
.hx-selected-template { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
.hx-selected-template>.hx-picture { width:96px; height:96px; flex-shrink:0; }
.hx-selected-template>div:not(.hx-picture) { flex:1; min-width:140px; }
.hx-selected-template strong { font-size:15px; }
.hx-checklist { display:flex; flex-wrap:wrap; gap:6px 16px; color:var(--art-gray-700); font-size:12px; }
.hx-checklist span::before { content:'·'; color:var(--el-color-primary); margin-right:4px; }
</style>
