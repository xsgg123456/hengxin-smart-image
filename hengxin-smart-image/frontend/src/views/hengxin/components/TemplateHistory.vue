<template>
  <ElDialog v-model="visible" title="模板历史版本" width="680px" @closed="emit('close')">
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
    <div v-loading="loading">
      <ElEmpty v-if="!loading && !versions.length && !error" description="暂无历史版本" />
      <ElCollapse v-model="expanded">
        <ElCollapseItem v-for="item in versions" :key="item.version" :name="item.version" :title="`v${item.version} · ${item.name}`">
          <p>{{ labels[item.mode] }} · {{ new Date(item.updatedAt).toLocaleString('zh-CN') }}</p>
          <p style="overflow-wrap:anywhere">保存的 Skill：{{ item.skill || '未绑定' }} <span v-if="item.skillVersionId">（{{ item.skillVersionId }}）</span></p>
          <p>绑定方式：{{ item.skillBinding === 'module_default' ? '保存时的模块默认' : '专用版本' }} · {{ item.images.length }} 张图片</p>
          <p v-if="item.notes">{{ item.notes }}</p>
          <ElTable :data="item.images" :max-height="360">
            <ElTableColumn type="index" label="顺序" width="60" />
            <ElTableColumn label="图片" width="110"><template #default="{ row }"><ElImage :src="row.url" :alt="row.name" fit="contain" style="width:80px;height:80px" :preview-src-list="item.images.map(p => p.url)" preview-teleported /></template></ElTableColumn>
            <ElTableColumn prop="name" label="文件名称" />
          </ElTable>
        </ElCollapseItem>
      </ElCollapse>
    </div>
    <template #footer><ElButton @click="visible = false">关闭</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { getTemplateVersions } from '@/api/templates'
import type { Template } from '@/types/hengxin'
import { labels } from '../model'
const props = defineProps<{ templateId: string }>()
const emit = defineEmits<{ close: [] }>()
const visible = ref(true), loading = ref(false), error = ref(''), versions = ref<Template[]>([]), expanded = ref<number[]>([])
let alive = true
onBeforeUnmount(() => { alive = false })
async function load() {
  if (loading.value) return
  loading.value = true; error.value = ''
  try {
    const result = await getTemplateVersions(props.templateId)
    if (alive) { versions.value = result; expanded.value = result.length ? [result[0]!.version] : [] }
  } catch (reason) { if (alive) error.value = reason instanceof Error ? reason.message : '历史版本加载失败' }
  finally { if (alive) loading.value = false }
}
void load()
</script>
