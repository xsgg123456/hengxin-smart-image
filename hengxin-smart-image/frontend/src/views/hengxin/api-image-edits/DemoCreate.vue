<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE WORKSPACE</span><h1>新建换图</h1><p>一份素材，逐张替换整套原图。上传图片，写下这次的修改要求。</p></div><ElButton @click="router.push('/api-image-edits/records')">换图记录 <ArtSvgIcon icon="ri:arrow-right-up-line" /></ElButton></div>
    <PreviewNotice />
    <div class="hx-create-grid">
      <div class="hx-stack">
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">01</span>上传原图与素材</h2><ElButton text type="primary" @click="fillExample">填入示例套图</ElButton></div>
          <ImageSequence v-model="preview.images" />
        </ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">02</span>填写修改要求</h2><span class="hx-muted">同一份要求应用于每张原图</span></div>
          <ElForm label-position="top">
            <ElFormItem label="任务名称" required><ElInput v-model="preview.name" aria-label="任务名称" placeholder="例如：秋日上新 · 手机屏幕套图" maxlength="60" show-word-limit /></ElFormItem>
            <ElFormItem label="提示词" required><ElInput v-model="preview.prompt" aria-label="提示词" type="textarea" :rows="5" maxlength="4000" show-word-limit placeholder="说明要替换的内容，以及哪些元素需要保持不变。" /></ElFormItem>
          </ElForm>
        </ElCard>
      </div>
      <aside class="hx-summary">
        <ElCard class="art-card hx-summary-card" shadow="never">
          <div class="hx-section-title"><h2>本次换图</h2><ElTag round>每批最多 10 张并行</ElTag></div>
          <div v-if="material" class="hx-summary-art"><PicturePreview :picture="material" title="共用素材" /><span>共用替换素材</span></div>
          <ElEmpty v-else description="添加图片后预览素材" :image-size="75" />
          <dl><div><dt>待修改原图</dt><dd>{{ originalCount }} 张</dd></div><div><dt>共用素材</dt><dd>{{ material ? '1 张' : '尚未添加' }}</dd></div><div><dt>预计输出</dt><dd>{{ originalCount }} 张</dd></div><div><dt>输出规格</dt><dd>1024 × 1024</dd></div></dl>
          <div class="hx-skill-note"><ArtSvgIcon icon="ri:refresh-line" /><div><strong>失败自动重试，最多 3 次</strong><small>等待 1 秒、2 秒、4 秒后依次重试</small></div></div>
          <p v-if="preview.pendingUploads" class="hx-footnote">正在读取图片，请稍候…</p>
          <p v-else-if="!valid" class="hx-footnote">请添加至少 1 张原图和 1 张素材，并填写任务名称与提示词。</p>
          <ElButton type="primary" size="large" class="hx-full hx-gap" :disabled="!valid" :loading="submitting" @click="submit">开始处理，共 {{ originalCount }} 张 <ArtSvgIcon icon="ri:arrow-right-line" /></ElButton>
          <p class="hx-footnote">预计 {{ Math.ceil(originalCount / 10) }} 批，当前批完成后开始下一批，结果按原图顺序展示。</p>
        </ElCard>
        <ElCard class="art-card hx-summary-card hx-gap" shadow="never"><div class="hx-section-title"><h2>演示场景</h2><ElTag type="info" size="small">仅预览</ElTag></div><ElSelect v-model="preview.scenario" aria-label="演示场景" class="hx-full"><ElOption label="重试后成功" value="retry" /><ElOption label="全部顺利完成" value="success" /><ElOption label="重试耗尽 · 部分失败" value="partial" /></ElSelect><p class="hx-footnote">选择提交后要体验的状态。图片均为示例，页面刷新后重置。</p></ElCard>
      </aside>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { preview, fillExample, submitPreview } from './preview-state'
import ImageSequence from './ImageSequence.vue'
import PreviewNotice from './PreviewNotice.vue'
import PicturePreview from '../components/PicturePreview.vue'
const router = useRouter()
const submitting = ref(false)
const material = computed(() => preview.images.at(-1))
const originalCount = computed(() => Math.max(0, preview.images.length - 1))
const valid = computed(() => !preview.pendingUploads && originalCount.value > 0 && !!preview.name.trim() && !!preview.prompt.trim())
async function submit() {
  if (submitting.value || !valid.value) return
  submitting.value = true
  try { const id = submitPreview(); await router.push({ path: '/api-image-edits/records', query: { task: id } }) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '提交失败，请重试') }
  finally { submitting.value = false }
}
</script>
