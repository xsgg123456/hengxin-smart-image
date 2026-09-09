<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">AI IMAGE WORKSPACE</span><h1>{{ labels[mode] }}</h1><p>{{ descriptions[mode] }}</p></div><ElButton @click="router.push('/tasks/index')">查看任务 <ArtSvgIcon icon="ri:arrow-right-up-line" /></ElButton></div>
    <div class="hx-create-grid">
      <div class="hx-stack">
        <ElCard v-if="mode !== 'text'" class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">01</span>选择套图模板</h2><ElButton text type="primary" @click="router.push('/templates/index')">管理模板 <ArtSvgIcon icon="ri:arrow-right-line" /></ElButton></div>
          <div class="hx-template-options">
            <button v-for="t in available" :key="t.id" type="button" class="hx-template-option" :class="{ selected: selected === t.id }" :aria-pressed="selected === t.id" @click="selected = t.id">
              <div class="hx-mini-mosaic"><img v-for="(p, i) in t.images.slice(0, 3)" :key="i" :src="p.url" :alt="p.name" /></div>
              <div class="hx-template-label"><strong>{{ t.name }}</strong><span>{{ t.images.length }} 张模板图 <i>{{ selected === t.id ? '已选择' : '选择模板' }}</i></span></div>
            </button>
          </div>
          <ElEmpty v-if="!available.length" description="暂无可用模板，请先创建模板" :image-size="75" />
        </ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">{{ mode === 'text' ? '01' : '02' }}</span>{{ mode === 'text' ? '上传待修改图片' : '上传替换素材' }}</h2><ElButton text type="primary" @click="useExample">使用示例素材</ElButton></div>
          <ElUpload drag multiple accept="image/png,image/jpeg,image/webp" :auto-upload="false" :show-file-list="false" :on-change="onUpload">
            <div class="hx-upload-icon"><ArtSvgIcon icon="ri:upload-cloud-2-line" /></div><strong>点击上传，或将图片拖到这里</strong><p>{{ mode === 'wallpaper' ? '上传希望放入手机屏幕的新壁纸' : mode === 'product' ? '上传希望替换到模板中的商品图片' : '上传需要替换文字的商品图片' }}</p><small>JPG / PNG / WebP · 原型单张上限 10 MB</small>
          </ElUpload>
          <div v-if="sources.length" class="hx-source-list"><div v-for="(p, i) in sources" :key="i" class="hx-source"><img :src="p.url" :alt="p.name" /><span>{{ p.name }}</span><ElButton text type="danger" :aria-label="`移除素材 ${i + 1}`" @click="sources.splice(i, 1)">移除</ElButton></div></div>
          <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon class="hx-gap" />
        </ElCard>
        <ElCard class="art-card hx-section" shadow="never">
          <div class="hx-section-title"><h2><span class="hx-number">{{ mode === 'text' ? '02' : '03' }}</span>任务信息</h2><span class="hx-muted">方便后续查找与归档</span></div>
          <ElForm label-position="top"><ElFormItem label="任务名称" required><ElInput v-model="name" placeholder="例如：秋日上新 · 手机屏幕套图" maxlength="60" show-word-limit /></ElFormItem><ElFormItem :label="mode === 'text' ? '文字修改要求' : '补充说明（选填）'" :required="mode === 'text'"><ElInput v-model="note" type="textarea" :rows="3" :placeholder="mode === 'text' ? '例如：将「夏日特惠」改为「秋日上新」，其余内容保持不变' : '告诉我们这次需要特别注意的地方'" maxlength="1000" /></ElFormItem></ElForm>
        </ElCard>
      </div>
      <aside class="hx-summary">
        <ElCard class="art-card hx-summary-card" shadow="never"><div class="hx-section-title"><h2>本次任务</h2><ElTag effect="light" round>新任务</ElTag></div>
          <div class="hx-summary-art"><img :src="template?.images[0]?.url || '/samples/text-0.svg'" alt="模板效果示例" /><span>模板效果示例</span></div>
          <dl><div><dt>处理类型</dt><dd>{{ labels[mode] }}</dd></div><div><dt>已选模板</dt><dd>{{ mode === 'text' ? '无需模板' : template?.name || '尚未选择' }}</dd></div><div><dt>替换素材</dt><dd>{{ sources.length }} 张</dd></div><div><dt>预计输出</dt><dd>{{ mode === 'text' ? sources.length : template?.images.length || 0 }} 张</dd></div></dl>
          <div class="hx-skill-note"><ArtSvgIcon icon="ri:sparkling-2-line" /><div><strong>{{ skills[mode] }}</strong><small>由系统自动调用 · 原型演示</small></div></div>
          <ElButton type="primary" size="large" class="hx-full" :loading="submitting" @click="submit"><ArtSvgIcon icon="ri:sparkling-line" /> 提交生成任务</ElButton><p class="hx-footnote">本页用于交互评审，生成返回示例图片。</p>
        </ElCard>
        <div class="hx-tips"><h3>每一次套图，都可以继续完善</h3><p>生成后支持整套或单张提出修改意见，满意后再归档到成品库。</p></div>
      </aside>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { UploadFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import { db, labels, skills, sampleImages, readPictures, createTask, type Mode, type Picture } from '../model'
const props = defineProps<{ mode: Mode }>()
const router = useRouter(), route = useRoute()
const descriptions = { wallpaper: '保留商品与画面设计，为整套图片换上新的屏幕壁纸。', product: '复用成熟的商品模板，让新商品自然融入原有场景。', text: '说清楚要改的文字，其余处理交给对应的 Skill。' }
const available = computed(() => db.templates.filter(t => t.mode === props.mode && t.active))
const selected = ref(String(route.query.template || available.value[0]?.id || ''))
watch(() => route.query.template, value => {
  if (typeof value === 'string' && available.value.some(t => t.id === value)) selected.value = value
})
const template = computed(() => available.value.find(t => t.id === selected.value))
const sources = ref<Picture[]>([]), name = ref(''), note = ref(''), error = ref(''), submitting = ref(false)
function useExample() { sources.value = sampleImages(props.mode, props.mode === 'text' ? 2 : 1); if (!name.value) name.value = props.mode === 'text' ? '秋日上新 · 文案更新' : props.mode === 'product' ? '新品钢化膜 · 商品主图' : '秋日山川 · 手机屏幕套图'; if (props.mode === 'text') note.value = '将「新品上市」改为「秋日上新」，其他内容保持不变'; error.value = '' }
async function onUpload(file: UploadFile) { if (!file.raw) return; try { sources.value.push(...await readPictures([file.raw])); error.value = '' } catch { ElMessage.error('图片读取失败，请换一张图片') } }
function submit() {
  if (submitting.value) return
  error.value = !sources.value.length ? '请先上传素材或使用示例素材' : !name.value.trim() ? '请填写任务名称' : props.mode !== 'text' && !template.value ? '请选择可用模板' : props.mode === 'text' && !note.value.trim() ? '请填写文字修改要求' : ''
  if (error.value) { ElMessage.warning(error.value); return }
  submitting.value = true
  const task = createTask(props.mode, name.value.trim(), template.value, sources.value)
  if (note.value.trim()) task.feedback.push(`初始要求：${note.value.trim()}`)
  router.push({ path: '/tasks/index', query: { task: task.id } })
}
</script>
