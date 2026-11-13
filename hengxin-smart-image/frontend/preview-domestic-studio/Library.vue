<template>
  <section class="hx-page domestic-library">
    <div class="hx-heading"><div><span class="hx-admin-kicker">PRODUCT LIBRARY</span><h1>成品库</h1><p>集中查看「相机配件生成」和「手机壳生成」的归档。</p></div><ElTag>{{ archives.length }} 套归档</ElTag></div>
    <div class="domestic-library-filters"><ElInput v-model="search" clearable aria-label="搜索产品名称" placeholder="搜索产品名称" :prefix-icon="Search" /><ElSelect v-model="source" aria-label="归档来源" placeholder="全部来源"><ElOption label="全部来源" value="" /><ElOption label="相机配件生成" value="相机配件生成" /><ElOption label="手机壳生成" value="手机壳生成" /></ElSelect><ElButton @click="search = ''; source = ''">重置</ElButton><span>本地预览 · 刷新后清空</span></div>
    <div v-if="!filtered.length" class="domestic-library-empty"><p>{{ archives.length ? '没有找到匹配的产品' : '暂无归档' }}</p><small>{{ archives.length ? '试试其他产品名称或来源。' : '在新品生成工作台完成设计后，点击「归档到成品库」。' }}</small></div>
    <div v-else class="domestic-library-grid"><article v-for="item in filtered" :key="item.id" class="domestic-library-card"><div class="library-card-title"><h2>{{ item.productName }}</h2><ElTag size="small" type="success">已归档</ElTag></div><p>{{ item.sourceTitle }}</p><dl><div><dt>原会话</dt><dd>{{ item.conversationName }}</dd></div><div><dt>归档时间</dt><dd>{{ archiveTime(item.createdAt) }}</dd></div></dl><p class="archive-preview-note">演示归档 · 暂无成品图片</p><div class="library-card-actions"><ElButton type="primary" plain @click="selected = item; detailTab = 'pictures'">查看归档</ElButton><ElButton text type="danger" @click="remove(item)">删除</ElButton></div></article></div>
    <ElDrawer :model-value="!!selected" title="归档详情" size="min(760px,100vw)" @close="selected = undefined">
      <template v-if="selected"><h2 class="archive-detail-title">{{ selected.productName }}</h2><p class="archive-detail-meta">{{ selected.sourceTitle }} · {{ archiveTime(selected.createdAt) }}</p><ElTabs v-model="detailTab"><ElTabPane label="成品图片" name="pictures"><div class="domestic-library-empty"><p>暂无成品图片</p><small>当前为交互预览，未调用真实生成。上传的附件保留在「对话与资料」中。</small></div></ElTabPane><ElTabPane label="对话与资料" name="conversation"><p class="archive-preview-note">归档时保存的副本，后续对话修改不会影响这里。</p><MessageItem v-for="message in selected.messages" :key="message.id" :message="message" @preview="previewAsset" /></ElTabPane></ElTabs></template>
    </ElDrawer>
    <ElDialog v-model="imageOpen" :title="imageTitle" width="min(860px,94vw)"><img class="asset-preview" :src="imageUrl" :alt="imageTitle"></ElDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { archives, archiveTime, removeArchive, type ProductArchive } from './archives'
import './library.css'
import MessageItem from './MessageItem.vue'
import type { Asset } from './state'
const imageOpen = ref(false), imageUrl = ref(''), imageTitle = ref('')
function previewAsset(asset: Asset) { if (asset.image) { imageUrl.value = asset.url; imageTitle.value = asset.name; imageOpen.value = true } else { const link = document.createElement('a'); link.href = asset.url; link.download = asset.name; link.click() } }
const search = ref(''), source = ref(''), selected = ref<ProductArchive>(), detailTab = ref('pictures')
const filtered = computed(() => archives.filter(item => item.productName.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase()) && (!source.value || item.sourceTitle === source.value)))
async function remove(item: ProductArchive) {
  try { await ElMessageBox.confirm(`删除「${item.productName}」的归档副本？原会话不受影响。`, '删除归档', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }); removeArchive(item); if (selected.value?.id === item.id) selected.value = undefined; ElMessage.success('归档已删除') }
  catch (reason) { if (reason !== 'cancel' && reason !== 'close') ElMessage.error('删除失败，请重试') }
}
</script>
