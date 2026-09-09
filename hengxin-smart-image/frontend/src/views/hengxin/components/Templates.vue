<template>
  <div class="hx-page">
    <div class="hx-heading">
      <div><span class="hx-eyebrow">YOUR TEMPLATE COLLECTION</span><h1>模板库</h1><p>把成熟的商品设计，沉淀为下一次创作的起点。</p></div>
      <ElButton type="primary" :disabled="!!deleting" @click="edit()"><ArtSvgIcon icon="ri:add-line" /> 新建模板</ElButton>
    </div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter">
        <ElRadioGroup v-model="mode" aria-label="模板类型">
          <ElRadioButton value="all">全部模板</ElRadioButton><ElRadioButton value="wallpaper">壁纸模板</ElRadioButton>
          <ElRadioButton value="product">商品模板</ElRadioButton>
        </ElRadioGroup>
        <ElInput v-model="search" clearable placeholder="搜索模板名称" aria-label="搜索模板名称" class="hx-search"><template #prefix><ArtSvgIcon icon="ri:search-line" /></template></ElInput>
        <ElSelect v-model="sort" class="hx-search" aria-label="模板排序">
          <ElOption value="updated" label="最近更新" /><ElOption value="name" label="名称排序" /><ElOption value="images" label="图片数量" />
        </ElSelect>
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon>
        <ElButton text type="primary" :disabled="loading" @click="load">重试加载</ElButton>
      </ElAlert>
      <div v-loading="loading" :aria-busy="loading">
        <div class="hx-library-grid">
          <ElCard v-for="t in templates" :key="t.id" class="art-card hx-library-card" shadow="never">
            <div class="hx-library-mosaic"><img v-for="(p, i) in t.images.slice(0, 4)" :key="i" :src="p.url" :alt="p.name" loading="lazy" /></div>
            <div class="hx-library-info">
              <div class="hx-row"><ElTag size="small" effect="plain">{{ labels[t.mode] }}</ElTag><ElTag size="small" :type="t.active && t.skillVersionId ? 'success' : 'info'">{{ t.active && t.skillVersionId ? '可使用' : '草稿 / 停用' }}</ElTag></div>
              <h3>{{ t.name }}</h3><p>{{ t.images.length }} 张模板图 <span>·</span> {{ t.skill || '尚未绑定 Skill' }}</p>
              <p>版本 v{{ t.version }} <span>·</span> {{ formatTime(t.updatedAt) }}</p>
              <div class="hx-row"><ElButton :disabled="loading || !!deleting || !t.active || !t.skillVersionId" type="primary" plain @click="use(t)">使用模板</ElButton><ElButton text :disabled="loading || !!deleting" @click="edit(t)">配置模板</ElButton></div>
              <div class="hx-gap"><ElButton text :disabled="loading || !!deleting" @click="historyId = t.id">历史版本</ElButton><ElButton text type="danger" :loading="deleting === t.id" :disabled="loading || !!deleting" @click="remove(t)">删除模板</ElButton></div>
            </div>
          </ElCard>
        </div>
        <ElEmpty v-if="!templates.length" :description="loading ? '正在加载模板…' : error ? '模板加载失败，请重试' : '暂无匹配模板，可新建或清除筛选'" />
      </div>
      <ElPagination v-model:current-page="page" class="hx-gap" :page-size="pageSize" :total="total" layout="prev, pager, next, total" :disabled="loading || !!deleting" />
    </ElCard>
    <TemplateEditor v-if="dialog" :template-id="editing" @close="dialog = false" @saved="saved" />
    <TemplateHistory v-if="historyId" :template-id="historyId" @close="historyId = ''" />
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listTemplates, deleteTemplate } from '@/api/templates'
import type { Mode, Template, TemplateQuery } from '@/types/hengxin'
import { labels } from '../model'
import TemplateEditor from './TemplateEditor.vue'
import TemplateHistory from './TemplateHistory.vue'

const router = useRouter()
const mode = ref<Mode | 'all'>('all'), search = ref(''), sort = ref<NonNullable<TemplateQuery['sort']>>('updated')
const templates = ref<Template[]>([]), total = ref(0), page = ref(1), pageSize = 12
const loading = ref(false), error = ref(''), dialog = ref(false), editing = ref<string>(), deleting = ref('')
const historyId = ref('')
let request = 0
function message(reason: unknown, fallback: string) { return reason instanceof Error ? reason.message : fallback }
async function load() {
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const result = await listTemplates({ page: page.value, pageSize, search: search.value.trim(), mode: mode.value === 'all' ? undefined : mode.value, sort: sort.value })
    if (current !== request) return
    const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
    if (page.value > lastPage) { page.value = lastPage; return }
    templates.value = result.items
    total.value = result.total
  } catch (reason) {
    if (current === request) { templates.value = []; total.value = 0; error.value = message(reason, '模板加载失败，请重试') }
  } finally { if (current === request) loading.value = false }
}
watch([mode, search, sort], () => { page.value = 1 }, { flush: 'sync' })
watch([mode, search, sort, page], load, { immediate: true })
onBeforeUnmount(() => { request++ })
function edit(template?: Template) { editing.value = template?.id; dialog.value = true }
function use(template: Template) { void router.push({ path: `/image-processing/${template.mode}`, query: { template: template.id } }) }
function saved() { dialog.value = false; void load() }
function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '更新时间未知' : date.toLocaleString('zh-CN', { hour12: false })
}
async function remove(template: Template) {
  if (deleting.value) return
  deleting.value = template.id
  try {
    try {
      await ElMessageBox.confirm(`删除“${template.name}”？历史任务中的图片会保留。`, '删除模板', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
    } catch { return }
    await deleteTemplate(template.id)
    ElMessage.success('模板已删除')
    await load()
  } catch (reason) { ElMessage.error(message(reason, '删除失败，请重试')) }
  finally { deleting.value = '' }
}
</script>
