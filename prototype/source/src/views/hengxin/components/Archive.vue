<template>
  <div class="hx-page"><div class="hx-heading"><div><span class="hx-eyebrow">FINISHED & COLLECTED</span><h1>成品库</h1><p>满意的作品，值得好好保存。随时查找、预览与下载。</p></div><ElTag effect="plain" size="large">{{ db.archives.length }} 套已归档</ElTag></div>
    <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter"><ElRadioGroup v-model="mode"><ElRadioButton value="all">全部成品</ElRadioButton><ElRadioButton v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</ElRadioButton></ElRadioGroup><ElInput v-model="search" placeholder="搜索成品名称" clearable class="hx-search" /></div><div class="hx-library-grid"><ElCard v-for="a in filtered" :key="a.id" class="art-card hx-library-card" shadow="never"><div class="hx-library-mosaic"><img v-for="(p, i) in a.images.slice(0, 4)" :key="i" :src="p.url" :alt="p.name" /></div><div class="hx-library-info"><ElTag size="small" type="success">已归档</ElTag><h3>{{ a.name }}</h3><p>{{ labels[a.mode] }} · {{ a.images.length }} 张图片</p><p>{{ a.time }}</p><div class="hx-row"><ElButton type="primary" plain @click="preview = a">查看成品</ElButton><ElButton text @click="downloadSet(a.images, a.name)">下载整套</ElButton><ElButton text type="danger" @click="remove(a)">删除</ElButton></div></div></ElCard></div><ElEmpty v-if="!filtered.length" description="这里还没有成品，满意的任务结果可以归档到这里"><ElButton @click="router.push('/tasks/index')">前往任务中心</ElButton></ElEmpty></ElCard>
    <ElDialog :model-value="!!preview" :title="preview?.name" width="80%" @close="preview = undefined"><p class="hx-muted">归档的示例图片 · 后续修改不会覆盖此版本</p><div v-if="preview" class="hx-result-grid"><div v-for="(p, i) in preview.images" :key="i"><ElImage :src="p.url" :preview-src-list="preview.images.map(x => x.url)" :initial-index="i" :alt="p.name" preview-teleported /><div class="hx-row"><span>{{ p.name }} · v{{ p.version || 1 }}</span><ElButton text type="primary" @click="downloadPicture(p)">下载</ElButton></div></div></div></ElDialog>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { db, labels, removeArchive, type Archive } from '../model'
import { downloadSet, downloadPicture } from '../download'
const router = useRouter(), mode = ref('all'), search = ref(''), preview = ref<Archive>()
const filtered = computed(() => db.archives.filter(a => (mode.value === 'all' || a.mode === mode.value) && a.name.includes(search.value)))
async function remove(a: Archive) { try { await ElMessageBox.confirm('删除这条原型归档？对应任务结果保留。', '删除成品', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }); removeArchive(a) } catch { /* cancelled */ } }
</script>
