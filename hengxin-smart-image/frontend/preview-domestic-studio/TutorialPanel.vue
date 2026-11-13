<template>
  <section class="tutorial-panel" aria-label="使用教程">
    <header class="tutorial-header"><div><span class="tutorial-eyebrow"><ElIcon><Reading /></ElIcon> 使用教程</span><h2>{{ config.title }}</h2></div><ElButton text :icon="Close" aria-label="关闭使用教程" @click="$emit('close')" /></header>
    <div class="tutorial-tabs" role="tablist" aria-label="教程类型"><button role="tab" :aria-selected="tab === 'steps'" aria-controls="tutorial-steps" :class="{ active: tab === 'steps' }" @click="tab = 'steps'">图文指南</button><button role="tab" :aria-selected="tab === 'video'" aria-controls="tutorial-video" :class="{ active: tab === 'video' }" @click="tab = 'video'">视频教程<span>待补充</span></button></div>
    <div :key="config.id + tab" class="tutorial-scroll">
      <template v-if="tab === 'steps'">
        <div id="tutorial-steps" role="tabpanel" aria-label="图文指南">
          <p class="tutorial-sample-note">以下为教程排版示例，正式内容待补充。</p>
          <div class="tutorial-overview"><strong>边看边做，不用离开工作台</strong><p>准备资料 → 描述要求 → 发送并继续修改</p></div>
          <div v-if="topics.length" class="tutorial-topics"><span>这次想做什么？</span><div><button v-for="topic in topics" :key="topic.label" :class="{ active: selectedTopic === topic.label }" @click="selectedTopic = topic.label">{{ topic.label }}</button></div><p>{{ topicHint }}</p></div>
          <ol class="tutorial-steps">
            <li><span class="tutorial-step-number">01</span><div><h3>准备并上传资料</h3><p>{{ config.primaryHint }}。{{ config.group === 'new' ? '可按需补充风格或构图参考。' : '需要替换时，再添加对应素材并说明用途。' }}</p><div class="tutorial-material-map"><div><ElIcon><Picture /></ElIcon><strong>{{ config.primaryRole }}</strong><small>要处理的主要资料</small></div><span>＋</span><div><ElIcon><Files /></ElIcon><strong>{{ config.secondaryRole }}</strong><small>{{ config.group === 'new' ? '参考效果 · 可选' : '根据修改要求添加' }}</small></div></div></div></li>
            <li><span class="tutorial-step-number">02</span><div><h3>说清楚你的要求</h3><p>{{ config.group === 'new' ? '写明图片用途、希望突出的卖点和喜欢的风格。不确定的地方可以在对话中补充。' : '说明要改什么、保留什么。多张素材时，标明每张图片的用途；修改尺寸时写出像素宽高。' }}</p><div class="tutorial-example"><div><span>示例要求</span><ElButton text size="small" :icon="DocumentCopy" @click="copy">{{ copied ? '已复制' : '复制' }}</ElButton></div><p>{{ config.example }}</p><ElButton size="small" plain type="primary" :icon="EditPen" @click="$emit('use-example', config.example)">填入输入框</ElButton><small>保留已有文字，不会自动发送</small></div></div></li>
            <li><span class="tutorial-step-number">03</span><div><h3>发送后，继续提出修改</h3><p>检查附件和要求后点击「发送」。需要调整时，在当前对话中继续描述，不用重新开始。</p></div></li>
          </ol>
          <div class="tutorial-faq"><h3>常见问题</h3><details><summary>需要自己选择 Skill 吗？</summary><p>不需要。正式接入后，当前业务入口会自动使用对应 Skill；预览不调用真实 Skill。</p></details><details><summary>关掉教程，资料和文字会丢吗？</summary><p>不会。教程的展开和关闭不会清空当前对话、附件或输入内容。</p></details></div>
        </div>
      </template>
      <div v-else id="tutorial-video" role="tabpanel" aria-label="视频教程" class="tutorial-video-content"><div class="tutorial-video-placeholder"><ElIcon><VideoCamera /></ElIcon><strong>视频教程正在整理</strong><p>{{ config.title }}</p><span>这里将展示对应的操作视频</span></div><h3>看完就能跟着操作</h3><p>后续可放置上传资料、填写要求、查看结果与继续修改的完整录屏。</p><ElButton plain @click="tab = 'steps'">先看图文指南</ElButton><small>当前仅预留视频位置，没有可播放内容。</small></div>
    </div>
    <footer class="tutorial-footer"><span>教程跟随当前业务入口切换</span><ElButton size="small" @click="$emit('close')">收起教程</ElButton></footer>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Reading, Close, Picture, Files, DocumentCopy, EditPen, VideoCamera } from '@element-plus/icons-vue'
import type { WorkspaceConfig } from './workspaces'
const props = defineProps<{ config: WorkspaceConfig }>()
defineEmits<{ close: []; 'use-example': [text: string] }>()
const tab = ref<'steps' | 'video'>('steps'), copied = ref(false), selectedTopic = ref('')
const topics = computed(() => props.config.id === 'scene' ? [
  { label: '换场景', hint: '描述目标场景、光线和氛围，并说明需要保留的主体。' },
  { label: '换模特', hint: '提供模特参考或描述外观、姿态，并说明产品如何展示。' },
  { label: '换产品', hint: '上传新产品素材，说明原图中需要替换的对象。' },
  { label: '修改尺寸', hint: '写出目标宽 × 高（像素），并说明希望裁切还是补充画面。' },
] : props.config.id === 'phone' ? [
  { label: '换手机', hint: '提供目标手机素材，注明机型、颜色和需要替换的区域。' },
  { label: '换壁纸', hint: '提供壁纸参考，说明只替换屏幕内容以及需要保留的反光、遮挡。' },
  { label: '换膜', hint: '提供保护膜素材或效果参考，说明膜边、开孔等需要呈现的细节。' },
] : [])
const topicHint = computed(() => topics.value.find(item => item.label === selectedTopic.value)?.hint)
watch(() => props.config.id, () => { tab.value = 'steps'; copied.value = false; selectedTopic.value = topics.value[0]?.label || '' }, { immediate: true })
async function copy() { try { await navigator.clipboard.writeText(props.config.example); copied.value = true } catch { ElMessage.warning('无法自动复制，请选中示例文字手动复制。') } }
</script>
