<template>
  <div class="text-reader">
    <div class="reader-tools">
      <ElSelect v-if="tabular" v-model="sheetIndex" aria-label="工作表" @change="page = 1">
        <ElOption v-for="(sheet, i) in sheets" :key="i" :label="sheet.name" :value="i" />
      </ElSelect>
      <span>{{ tabular ? '表格内容预览' : '文本内容预览' }} · 不代表原始版式</span>
      <ElButton :disabled="page <= 1" aria-label="上一页" @click="page--">上一页</ElButton>
      <span>{{ page }} / {{ total }}</span><ElButton :disabled="page >= total" aria-label="下一页" @click="page++">下一页</ElButton>
      <ElButton :disabled="zoom <= 80" aria-label="缩小" @click="zoom -= 10">−</ElButton><span>{{ zoom }}%</span><ElButton :disabled="zoom >= 150" aria-label="放大" @click="zoom += 10">＋</ElButton>
    </div>
    <div class="reader-paper" tabindex="0" aria-label="资料内容，可滚动阅读">
      <table v-if="tabular" :style="{ fontSize: `${13 * zoom / 100}px` }"><tbody>
        <tr v-for="(row, index) in visibleRows" :key="index"><th>{{ (page - 1) * 50 + index + 1 }}</th><td v-for="(cell, j) in row" :key="j">{{ cell }}</td></tr>
      </tbody></table>
      <pre v-else :style="{ fontSize: `${14 * zoom / 100}px` }">{{ pages[page - 1] }}</pre>
    </div>
    <p class="hx-muted">可下载原文件，用本地软件核对完整格式、图片与公式。</p>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { materialSheets, materialTextPages } from './material-reader-data'
const props = defineProps<{ text: string; name: string }>()
const tabular = computed(() => /\.(xlsx?|csv)$/i.test(props.name))
const sheets = computed(() => materialSheets(props.text)), pages = computed(() => materialTextPages(props.text))
const page = ref(1), sheetIndex = ref(0), zoom = ref(100)
const rows = computed(() => sheets.value[sheetIndex.value]?.rows || [])
const total = computed(() => tabular.value ? Math.max(1, Math.ceil(rows.value.length / 50)) : pages.value.length)
const visibleRows = computed(() => rows.value.slice((page.value - 1) * 50, page.value * 50))
watch(() => [props.text, props.name], () => { page.value = 1; sheetIndex.value = 0; zoom.value = 100 })
</script>
<style scoped>
.reader-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px; background: #f6f8fc; font-size: 12px; color: #7b899d; }
.reader-tools .el-select { width: 150px; }.reader-tools .el-button { margin: 0; }
.reader-paper { background: #edf0f5; padding: 22px; max-height: 600px; overflow: auto; min-height: 300px; }
pre { background: white; padding: 28px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.9; margin: 0; }
table { background: white; border-collapse: collapse; min-width: 100%; } td, th { white-space: pre-wrap; min-width: 110px; padding: 12px; border: 1px solid #e3e8ef; } th { min-width: 40px; color: #8996a8; font-weight: normal; background: #f7f9fc; }
.hx-muted { font-size: 12px; margin-top: 12px; }
</style>
