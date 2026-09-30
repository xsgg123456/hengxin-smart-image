<template>
  <main class="record-background" aria-label="换图记录截图背景">
    <div class="preview-launcher"><span>交互预览 · 不会发起生成</span><ElButton type="primary" @click="open = true">修改这张</ElButton></div>
  </main>
  <ElDialog v-model="open" title="修改第 1 张图片 · 基于 V1" width="min(1380px, 96vw)" align-center :close-on-click-modal="false" class="single-edit-dialog">
    <div class="edit-mode-row">
      <ElRadioGroup v-model="mode" aria-label="修改类型"><ElRadioButton value="image">图片修改</ElRadioButton><ElRadioButton value="text">文字修改</ElRadioButton></ElRadioGroup>
      <span>{{ mode === 'image' ? '调整画面元素的位置、形态及局部细节' : '替换指定文字，保留原有字体样式与布局' }}</span>
      <ElButton text type="primary" @click="fixedPromptOpen = true">查看固定提示词</ElButton>
    </div>
    <AnnotationEditor ref="editor" :draft-key="`single-edit-preview-${mode}`" :load-original="loadOriginal" :base-label="`本次基于 V1 · ${modeLabel}`" :limit="4000" marking-optional require-text :preview-prompt="prompt" :description="description" confirm-label="确认修改（演示）" @submit="submitted" />
    <template #footer><span class="preview-note">交互预览 · 素材取自截图 · 不会发起生成</span><ElButton @click="open = false">关闭</ElButton><ElButton type="primary" @click="editor?.preview()">预览提交内容</ElButton></template>
  </ElDialog>
  <ElDialog v-model="fixedPromptOpen" :title="`${modeLabel} · 固定提示词`" width="min(760px, 94vw)" align-center append-to-body>
    <p class="hx-footnote">这是通用规则。具体改什么由你本次填写的修改意见决定，提交时填入下方占位处。</p>
    <pre style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto;font:inherit;line-height:1.7">{{ fixedPrompt }}</pre>
    <template #footer><ElButton @click="fixedPromptOpen = false">返回修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AnnotationEditor from '../src/views/hengxin/components/annotation/AnnotationEditor.vue'
import { buildTextEditPrompt, TEXT_EDIT_TEMPLATE } from '../src/views/hengxin/api-image-edits/text-edit-prompt'
import { buildImageEditPrompt, IMAGE_EDIT_TEMPLATE } from './image-edit-prompt'
import phoneUrl from './phone.svg?url'
const open = ref(true), mode = ref<'image' | 'text'>('image')
const fixedPromptOpen = ref(false)
const editor = ref<InstanceType<typeof AnnotationEditor>>()
const modeLabel = computed(() => mode.value === 'image' ? '图片修改' : '文字修改')
const description = computed(() => mode.value === 'image'
  ? '按你填写的意见编辑指定元素或区域；保留未指定修改的内容。适用于不同图片，标注仅用于定位，不进入成品。'
  : '仅以当前成品和可选标注为输入，按意见修改文字；默认保留字体风格、字重、字号、颜色及布局，标注不进入成品。')
const prompt = computed(() => mode.value === 'text' ? buildTextEditPrompt : buildImageEditPrompt)
const fixedPrompt = computed(() => mode.value === 'text' ? TEXT_EDIT_TEMPLATE : IMAGE_EDIT_TEMPLATE)
async function loadOriginal() {
  const response = await fetch(phoneUrl)
  if (!response.ok) throw new Error('预览素材加载失败')
  return response.blob()
}
function submitted() { ElMessage.success(`已演示「${modeLabel.value}」提交；未调用生图接口，未创建新版本。`) }
</script>
