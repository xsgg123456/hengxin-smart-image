<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE WORKSPACE</span><h1>新建换图</h1><p>一份素材，逐张替换整套原图。上传图片，写下这次的修改要求。</p></div><ElButton @click="router.push('/api-image-edits/records')">换图记录 <ArtSvgIcon icon="ri:arrow-right-up-line" /></ElButton></div>
    <ChannelNotice :status="status" :error="error" :loading="loading" :admin="isAdmin" :busy="busy" @refresh="load" @resume="resume" />
    <ElAlert v-if="state.error" :title="state.error" type="error" :closable="false" class="hx-gap" />
    <ElAlert v-if="state.pending" title="正在确认原提交结果，输入暂时锁定" description="再次确认使用同一个请求，不会创建新的本地任务。请勿重复选择图片提交。" type="warning" :closable="false" class="hx-gap" />
    <div class="hx-create-grid">
      <div class="hx-stack">
        <ElCard class="art-card hx-section" shadow="never"><div class="hx-section-title"><h2><span class="hx-number">01</span>上传原图与素材</h2></div><RealImageSequence :draft="draft" :disabled="blocked" /></ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">02</span>填写修改要求</h2><span class="hx-muted">同一份要求应用于每张原图</span></div>
          <ElForm label-position="top" :disabled="draft.locked()"><ElFormItem label="任务名称" required><ElInput v-model="state.name" aria-label="任务名称" placeholder="例如：秋日上新 · 手机屏幕套图" maxlength="60" show-word-limit /></ElFormItem><ElFormItem label="提示词" required><ElInput v-model="state.prompt" aria-label="提示词" type="textarea" :rows="5" maxlength="4000" show-word-limit placeholder="说明要替换的内容，以及哪些元素需要保持不变。" /></ElFormItem></ElForm>
        </ElCard>
      </div>
      <aside class="hx-summary"><ElCard class="art-card hx-summary-card" shadow="never">
        <div class="hx-section-title"><h2>本次换图</h2><ElTag round>串行处理</ElTag></div>
        <div v-if="material" class="hx-summary-art"><PicturePreview :picture="material" title="共用素材" /><span>共用替换素材</span></div><ElEmpty v-else description="添加图片后预览素材" :image-size="75" />
        <dl><div><dt>待修改原图</dt><dd>{{ originalCount }} 张</dd></div><div><dt>共用素材</dt><dd>{{ material || state.pending ? '1 张' : '尚未添加' }}</dd></div><div><dt>预计输出</dt><dd>{{ originalCount }} 张</dd></div><div><dt>请求规格</dt><dd>1024 × 1024</dd></div></dl>
        <div class="hx-skill-note"><ArtSvgIcon icon="ri:refresh-line" /><div><strong>可恢复错误自动重试，最多 3 次</strong><small>等待 1 秒、2 秒、4 秒后依次重试</small></div></div>
        <p v-if="state.images.some(p => p.state !== 'ready')" class="hx-footnote">请等待上传完成，并重传或移除失败图片。</p><p v-else-if="!draft.valid()" class="hx-footnote">请添加至少 1 张原图和 1 张素材，并填写任务名称与提示词。</p>
        <ElButton type="primary" size="large" class="hx-full hx-gap" :loading="state.busy" :disabled="state.busy || (!state.pending && (blocked || !draft.valid()))" @click="submit">{{ state.pending ? '再次确认原提交结果' : `开始处理，共 ${originalCount} 张` }} <ArtSvgIcon icon="ri:arrow-right-line" /></ElButton>
        <p class="hx-footnote">逐张处理，结果按原图顺序展示。请求结果不确定时需管理员核实。</p>
      </ElCard></aside>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import PicturePreview from '../components/PicturePreview.vue'
import RealImageSequence from './RealImageSequence.vue'
import ChannelNotice from './ChannelNotice.vue'
import { useChannel } from './use-channel'
import { draftForUser } from './real-draft'
import { useUserStore } from '@/store/modules/user'
const draft = draftForUser(String(useUserStore().getUserInfo.userId))
const router = useRouter(), state = draft.state
const { status, error, loading, busy, isAdmin, blocked, load, resume } = useChannel()
const material = computed(() => state.images.at(-1)), originalCount = computed(() => state.pending?.input.originalFileIds.length ?? Math.max(0, state.images.length - 1))
async function submit() { const id = await draft.submit(); if (id) await router.push({ path: '/api-image-edits/records', query: { task: id } }) }
</script>
