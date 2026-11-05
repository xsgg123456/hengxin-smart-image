<template>
  <section class="reference-panel" aria-label="参考图">
    <div class="reference-heading"><h3>参考图 <small>选填 · {{ draft.references.length }}张</small></h3><ElButton size="small" type="primary" plain :disabled="disabled" @click="input?.click()">＋ 上传参考图</ElButton></div>
    <p class="hx-footnote">仅用于修改当前图片。上传后，请逐张说明要参考什么。</p>
    <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden aria-label="上传参考图文件" :disabled="disabled" @change="upload" />
    <div v-if="!draft.references.length" class="reference-empty" @dragover.prevent @drop.prevent="drop"><span>上传参考图片，用途可选择或自定义</span><small>JPG / PNG / WebP · 单张最大20 MB</small></div>
    <article v-for="(item, i) in draft.references" :key="item.id" class="reference-card">
      <div class="reference-top">
        <ElImage v-if="item.status === 'ready'" :src="item.url" :alt="item.name" fit="contain" :preview-src-list="[item.url]" preview-teleported :z-index="6500" />
        <div v-else class="reference-placeholder">{{ item.status === 'loading' ? '读取中…' : '读取失败' }}</div>
        <div class="reference-name"><strong>参考图{{ i + 1 }}</strong><small :title="item.name">{{ item.name }}</small><div><ElButton text size="small" :disabled="disabled" @click="replacing = item; replacement?.click()">替换</ElButton><ElButton text size="small" type="danger" :disabled="disabled" @click="removeReference(draft, item)">删除</ElButton></div></div>
      </div>
      <p v-if="item.status === 'error'" class="reference-error" role="alert">{{ item.error }} <ElButton text size="small" :disabled="disabled" @click="readReference(item)">重试</ElButton></p>
      <label :for="`kind-${item.id}`">这是什么图 <span>*</span></label>
      <ElSelect :id="`kind-${item.id}`" v-model="item.kind" :aria-label="`参考图${i + 1}用途`" placeholder="请选择图片用途" :disabled="disabled"><ElOption label="本产品实拍" value="product" /><ElOption label="成品效果参考" value="effect" /><ElOption label="自定义用途" value="custom" /></ElSelect>
      <template v-if="item.kind === 'custom'">
        <label :for="`purpose-${item.id}`">自定义图片用途 <span>*</span></label>
        <ElInput :id="`purpose-${item.id}`" v-model="item.customPurpose" :aria-label="`参考图${i + 1}自定义用途`" type="textarea" :rows="2" maxlength="2000" placeholder="请自由填写这张图片的用途" :disabled="disabled" />
      </template>
      <label :for="`note-${item.id}`">要参考什么 <span>*</span></label>
      <ElInput :id="`note-${item.id}`" v-model="item.note" :aria-label="`参考图${i + 1}说明`" type="textarea" :rows="2" maxlength="2000" :disabled="disabled" :placeholder="item.kind === 'product' ? '例如：参考商品的结构和颜色，不参考背景。' : item.kind === 'effect' ? '例如：参考商品摆放角度，不照搬商品款式。' : '请说明需要参考的内容，以及希望如何修改。'" />
    </article>
    <input ref="replacement" type="file" accept="image/jpeg,image/png,image/webp" hidden aria-label="替换参考图文件" @change="replace" />
  </section>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { addReferences, readReference, removeReference, type Draft, type Reference } from './state'
const props = defineProps<{ draft: Draft; disabled: boolean }>()
const input = ref<HTMLInputElement>(), replacement = ref<HTMLInputElement>(), replacing = ref<Reference>()
function upload(event: Event) { const el = event.target as HTMLInputElement; if (!props.disabled) addReferences(props.draft, Array.from(el.files || [])); el.value = '' }
function drop(event: DragEvent) { if (!props.disabled) addReferences(props.draft, Array.from(event.dataTransfer?.files || [])) }
function replace(event: Event) { const el = event.target as HTMLInputElement, file = el.files?.[0], item = replacing.value; if (file && item && props.draft.references.some(r => r.id === item.id) && !props.disabled) { item.file = file; item.name = file.name; item.asset = undefined; void readReference(item) }; el.value = '' }
</script>
