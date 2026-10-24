<template>
  <ElButton ref="expandButton" text :disabled="disabled" :icon="FullScreen" @click="open = true">展开编辑</ElButton>
    <ElDialog v-model="open" title="展开编辑设计要求" width="min(960px,94vw)" top="8vh" append-to-body :close-on-click-modal="false" class="studio-text-editor" @opened="editor?.focus()" @closed="expandButton?.$el?.focus()">
      <p class="studio-text-editor-note">{{ sessionName }} · 在这里完整查看和编辑，关闭后文字会保留。</p>
      <ElInput ref="editor" v-model="text" type="textarea" resize="none" :disabled="disabled" aria-label="展开的设计要求" placeholder="描述设计要求，或继续提出修改意见…" />
      <template #footer><div class="studio-text-editor-footer"><span>{{ text.length }} 字 · Enter 换行，返回输入框后发送</span><ElButton type="primary" @click="open = false">完成编辑</ElButton></div></template>
    </ElDialog>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElButton, ElInput } from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
const text = defineModel<string>({ required: true })
defineProps<{ disabled?: boolean; sessionName: string }>()
const open = ref(false)
const editor = ref<InstanceType<typeof ElInput>>()
const expandButton = ref<InstanceType<typeof ElButton>>()
</script>
<style scoped>
:deep(.el-textarea__inner){height:clamp(200px,55dvh,620px)!important;font-size:16px;line-height:1.8;padding:16px;box-shadow:0 0 0 1px var(--el-border-color) inset!important}
.studio-text-editor-note{margin:0 0 14px;color:var(--art-gray-600);font-size:13px}
.studio-text-editor-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.studio-text-editor-footer>span{font-size:12px;color:var(--art-gray-600)}
</style>
