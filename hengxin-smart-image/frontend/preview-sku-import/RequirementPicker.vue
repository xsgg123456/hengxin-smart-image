<template>
  <ElDialog v-model="open" title="选择要导入的需求" width="860px" class="sku-picker" :close-on-click-modal="false">
    <p class="picker-note">SKU <strong>{{ sku }}</strong> 共找到 {{ items.length }} 条需求。选择一条，回填信息并导入该条需求的全部附件。</p>
    <ElRadioGroup v-model="selected" class="requirement-options" aria-label="选择需求">
      <label v-for="item in items" :key="item.id" class="requirement-option" :class="{ chosen: selected === item.id }">
        <ElRadio :value="item.id" :aria-label="item.title"><span class="sr-only">{{ item.title }}</span></ElRadio>
        <div class="requirement-copy">
          <div class="requirement-title"><strong>{{ item.title }}</strong><ElTag :type="item.status === '已完成' ? 'info' : 'success'" size="small">{{ item.status }}</ElTag></div>
          <p>品牌：{{ item.brandName }}<span>平台：{{ item.platformName }}</span></p>
          <p>设计师：{{ item.designerName }}<span>创建：{{ item.createdAt }}</span><span>{{ item.files.length }} 个附件</span></p>
          <p class="source-id">{{ item.id }}</p>
        </div>
      </label>
    </ElRadioGroup>
    <div v-if="chosen" class="selected-files"><strong>将导入 {{ chosen.files.length }} 个附件</strong><p v-for="file in chosen.files" :key="file.id">{{ file.filename }}</p></div>
    <template #footer><ElButton @click="open = false">取消</ElButton><ElButton type="primary" :disabled="!chosen" :loading="busy" @click="chosen && $emit('confirm', chosen)">使用这条需求</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Requirement } from './fixtures'
const open = defineModel<boolean>({ required: true })
const selected = defineModel<string>('selected', { required: true })
const props = defineProps<{ items: Requirement[]; sku: string; busy: boolean }>()
defineEmits<{ confirm: [record: Requirement] }>()
const chosen = computed(() => props.items.find(r => r.id === selected.value))
</script>
<style scoped>
.picker-note{color:var(--el-text-color-regular);line-height:1.7;margin-bottom:18px}.requirement-options{display:flex;flex-direction:column;width:100%;gap:12px}.requirement-option{width:100%;display:flex;gap:12px;align-items:flex-start;padding:16px;border:1px solid var(--el-border-color);border-radius:10px;cursor:pointer}.requirement-option.chosen{border-color:var(--el-color-primary);background:var(--el-color-primary-light-9)}.requirement-option:focus-within{outline:2px solid var(--el-color-primary);outline-offset:2px}.requirement-option :deep(.el-radio){margin:0;height:24px}.requirement-option :deep(.el-radio__label){padding:0}.requirement-copy{flex:1;min-width:0}.requirement-title{display:flex;align-items:flex-start;gap:12px;justify-content:space-between}.requirement-title strong{font-size:14px;line-height:1.7;overflow-wrap:anywhere}.requirement-title .el-tag{flex-shrink:0}.requirement-copy p{font-size:12px;line-height:1.9;margin-top:5px;color:var(--el-text-color-regular);display:flex;flex-wrap:wrap;gap:0 18px}.source-id{color:var(--el-text-color-secondary)!important}.selected-files{margin-top:16px;padding:14px;background:var(--el-fill-color-light);border-radius:8px;font-size:13px}.selected-files p{margin-top:8px;overflow-wrap:anywhere;line-height:1.6}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
</style>
