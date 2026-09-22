<template>
  <ElDialog v-model="open" title="选择套图模板" width="min(1120px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close class="hx-template-dialog">
    <div class="hx-picker-toolbar"><ElInput v-model="search" placeholder="搜索可用模板" aria-label="搜索可用模板" clearable :disabled="disabled" /><span>共 {{ total }} 套 · 点击图片可查看整套</span></div>
    <div v-loading="loading" class="hx-picker-content">
      <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="$emit('retry')">重试加载</ElButton></ElAlert>
      <div class="hx-template-options">
        <div v-for="t in templates" :key="t.id" class="hx-template-option" :class="{ selected: selectedId === t.id }">
          <PictureMosaic :pictures="t.images" :title="t.name" />
          <div class="hx-picker-identity"><strong>{{ t.name }}</strong><div><small>{{ t.images.length }} 张 · v{{ t.version }}</small><ElTag v-if="selectedId === t.id" size="small" type="success">✓ 当前使用</ElTag></div></div>
          <div class="hx-picker-footer"><span v-if="selectedId === t.id" class="hx-picker-current">已选择此模板</span><ElButton v-else class="hx-picker-action" :disabled="disabled || loading" @click="$emit('select', t)">使用此模板</ElButton></div>
        </div>
      </div>
      <ElEmpty v-if="!templates.length && !error" :description="loading ? '正在加载模板…' : '暂无匹配模板，请调整搜索或到模板库创建'" :image-size="64" />
    </div>
    <template #footer><div class="hx-picker-bottom"><ElPagination v-model:current-page="page" :page-size="pageSize" :total="total" :disabled="loading || disabled" layout="prev, pager, next" /><ElButton @click="open = false">{{ selectedId ? '取消更换' : '关闭' }}</ElButton></div></template>
  </ElDialog>
</template>
<script setup lang="ts">
import type { Template } from '@/types/hengxin'
import PictureMosaic from './PictureMosaic.vue'
const open = defineModel<boolean>({ required: true })
const search = defineModel<string>('search', { required: true })
const page = defineModel<number>('page', { required: true })
defineProps<{ templates: Template[]; selectedId?: string; total: number; pageSize: number; loading: boolean; error: string; disabled: boolean }>()
defineEmits<{ select: [template: Template]; retry: [] }>()
</script>
<style scoped>
.hx-picker-toolbar { display:flex; align-items:center; gap:16px; margin-bottom:16px; }
.hx-picker-toolbar .el-input { max-width:360px; }
.hx-picker-toolbar>span { color:var(--art-gray-600); font-size:12px; }
.hx-picker-content { max-height:calc(90vh - 180px); overflow-y:auto; padding:2px; }
.hx-template-options { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }
.hx-template-option { display:flex; flex-direction:column; min-width:0; border:1px solid var(--default-border); border-radius:12px; overflow:hidden; background:var(--default-box-color); }
.hx-template-option.selected { border-color:var(--el-color-primary); box-shadow:none; }
.hx-template-option :deep(.hx-picture-cell) { height:104px; aspect-ratio:auto; }
.hx-template-option :deep(.hx-picture-cell>.hx-picture) { height:100%; aspect-ratio:auto; }
.hx-template-option :deep(.hx-picture-count) { display:none; }
.hx-template-option :deep(.hx-picture-more) { inset:auto 4px 4px auto; padding:3px 6px; font-size:12px; }
.hx-picker-identity { padding:12px 12px 0; }
.hx-picker-identity strong { display:block; font-size:14px; line-height:1.5; overflow-wrap:anywhere; }
.hx-picker-identity>div { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:8px; min-height:24px; }
.hx-picker-identity small { color:var(--art-gray-600); }
.hx-picker-footer { padding:12px; margin-top:auto; }
.hx-picker-action { width:100%; min-height:36px; }
.hx-picker-current { display:flex; align-items:center; justify-content:center; min-height:36px; color:var(--art-gray-600); font-size:13px; }
.hx-picker-bottom { display:flex; justify-content:space-between; align-items:center; gap:12px; }
@media(max-width:800px) { .hx-template-options { grid-template-columns:repeat(2,minmax(0,1fr)); } .hx-picker-toolbar { flex-wrap:wrap; gap:8px; } }
@media(max-width:500px) { .hx-template-options { grid-template-columns:1fr; } }
</style>
