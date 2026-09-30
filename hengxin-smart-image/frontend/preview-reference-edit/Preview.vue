<template>
 <main class="record-background"><div class="preview-launcher"><span>多图参考 · 交互预览</span><ElButton type="primary" @click="open=true">修改这张</ElButton></div></main>
 <ElDialog v-model="open" title="修改第 4 张图片 · 基于 V1" width="min(1460px,96vw)" align-center :close-on-click-modal="false" class="reference-dialog">
  <div class="edit-mode-row"><ElRadioGroup v-model="mode" :disabled="locked" aria-label="修改类型"><ElRadioButton value="image">图片修改</ElRadioButton><ElRadioButton value="text">文字修改</ElRadioButton></ElRadioGroup><span>{{ mode==='image'?'对照原图与素材，仅优化你指定的内容':'仅修改文字，保留其他画面内容' }}</span><ElButton text type="primary" :disabled="locked" @click="fixedOpen=true">查看固定提示词</ElButton></div>
  <PreviewEditor ref="editor" :draft-key="`reference-preview-${mode}`" :load-original="loadOriginal" :base-label="`本次基于 V1 · ${mode==='image'?'图片修改':'文字修改'}`" :limit="4000" marking-optional require-text :preview-prompt="prompt" :description="mode==='image'?'当前成品是编辑底图，原图与素材仅作对照。只修改你明确指定的内容，其他部分保持不变。':'仅传当前成品和可选标注图，不附带原图与素材。'" confirm-label="确认修改（演示）" @preview-state="locked=$event" @submit="submitted">
   <template #references="{hasAnnotation,marks}">
    <div class="input-header"><strong>本轮输入图片 <span>{{ (mode==='image'?3:1)+(hasAnnotation?1:0) }} 张</span></strong><small>系统自动带入 · 点击图片放大对照</small></div>
    <div class="input-strip" :class="{textmode:mode==='text'}">
     <button v-for="(item,index) in references" :key="item.name" class="input-card" @click="showImage(item)"><img :src="item.url" :alt="item.name"><div><b>图{{ index+1 }} · {{ item.name }}</b><span>{{ item.role }}</span><small>{{ item.size }} · 点击放大</small></div></button>
     <div class="input-card annotation-card" :class="{included:hasAnnotation}"><div class="annotation-icon">✎</div><div><b>{{ hasAnnotation?`图${mode==='image'?4:2} · 标注图`:'标注图（可选）' }}</b><span>{{ hasAnnotation?(marks?`画布已标注 ${marks} 处`:'已上传标注图'):'在下方画布圈选' }}</span><small>{{ hasAnnotation?'提交时自动附带':'未标注，不发送此图' }}</small></div></div>
    </div>
    <div class="canvas-label"><strong>当前成品 · 标注画布</strong><span>可直接填写意见，也可圈出问题后逐处说明</span></div>
   </template>
   <template #example><ElButton v-if="mode==='image'" text type="primary" class="example-button" :disabled="locked" @click="editor?.fillExample()">填入这张图的示例意见</ElButton></template>
   <template #inputs="{annotationUrl}">
    <div class="confirm-input-title">本轮将发送 {{ references.length+(annotationUrl?1:0) }} 张图片 <small>顺序与提示词一致</small></div>
    <div class="confirm-images"><button v-for="(item,index) in references" :key="item.name" class="confirm-card" @click="showImage(item)"><img :src="item.url" :alt="item.name"><b>图{{ index+1 }} · {{ item.name }}</b><small>{{ item.role }}</small></button><button v-if="annotationUrl" class="confirm-card" @click="showImage({name:'标注图',url:annotationUrl,role:'仅用于定位',size:'800 × 800'})"><img :src="annotationUrl" alt="标注图"><b>图{{ references.length+1 }} · 标注图</b><small>仅用于定位，不进入成品</small></button></div>
    <p v-if="!annotationUrl" class="hx-footnote">本次未标注，按文字意见定位修改。</p>
   </template>
  </PreviewEditor>
  <template #footer><span class="preview-note">交互预览 · 不会发起生成</span><ElButton @click="open=false">关闭</ElButton><ElButton type="primary" @click="editor?.preview()">预览提交内容</ElButton></template>
 </ElDialog>
 <ElDialog v-model="zoomOpen" :title="zoomImage?.name+' · '+zoomImage?.size" width="min(860px,92vw)" align-center append-to-body><p class="hx-footnote">{{ zoomImage?.role }} · 关闭后继续在成品画布标注</p><img class="zoom-image" :src="zoomImage?.url" :alt="zoomImage?.name"><template #footer><ElButton @click="zoomOpen=false">返回编辑</ElButton></template></ElDialog>
 <ElDialog v-model="fixedOpen" title="固定提示词" width="min(780px,92vw)" align-center append-to-body><pre class="fixed-template">{{ mode==='image'?IMAGE_EDIT_TEMPLATE:TEXT_EDIT_TEMPLATE }}</pre><template #footer><ElButton @click="fixedOpen=false">返回编辑</ElButton></template></ElDialog>
</template>
<script setup lang="ts">
import {computed,ref} from 'vue'
import {ElMessage} from 'element-plus'
import PreviewEditor from './PreviewEditor.vue'
import current from './current.png?url'
import original from './original.jpg?url'
import material from './material.png?url'
import {IMAGE_EDIT_TEMPLATE,buildImageEditPrompt} from './image-edit-prompt'
import {TEXT_EDIT_TEMPLATE,buildTextEditPrompt} from '../src/views/hengxin/api-image-edits/text-edit-prompt'
const open=ref(true),mode=ref('image'),locked=ref(false),fixedOpen=ref(false),zoomOpen=ref(false)
const editor=ref<InstanceType<typeof PreviewEditor>>()
type Reference={name:string;url:string;role:string;size:string}
const zoomImage=ref<Reference>()
const all:Reference[]=[{name:'当前成品',url:current,role:'V1 · 本次编辑底图',size:'800 × 800'},{name:'对应原图',url:original,role:'参考构图与空间关系',size:'800 × 800'},{name:'共用素材',url:material,role:'参考对象外观与细节',size:'1440 × 1440'}]
const references=computed(()=>mode.value==='image'?all:all.slice(0,1))
const prompt=computed(()=>mode.value==='image'?buildImageEditPrompt:buildTextEditPrompt)
function showImage(item:Reference){zoomImage.value=item;zoomOpen.value=true}
async function loadOriginal(){const r=await fetch(current);if(!r.ok)throw new Error('图片加载失败');return r.blob()}
function submitted(){ElMessage.success('演示完成：已展示本轮图片与提示词，未提交生成请求。')}
</script>
