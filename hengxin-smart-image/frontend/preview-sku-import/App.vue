<template>
  <OverseasShell>
    <template #account><ElTag>海外业务</ElTag><ElButton text @click="explain">切换业务</ElButton><ElButton text @click="explain">退出登录</ElButton></template>
    <div class="preview-toolbar">
      <span class="preview-label">交互预览 · 示例数据</span>
      <ElSelect v-model="scenario" aria-label="预览场景" placeholder="选择一个示例 SKU" :disabled="locked || choosing" @change="loadScenario" style="width:300px"><ElOption v-for="s in scenarios" :key="s.sku" :value="s.sku" :label="s.label" /></ElSelect>
      <ElButton :disabled="locked || choosing" @click="clear">重置表单</ElButton>
      <ElSwitch v-model="baseline" aria-label="对照现有页面" :disabled="locked || choosing" active-text="对照现有页面" />
      <span class="preview-hint">选择示例后，点击「获取需求」体验；仅演示，不提交真实任务。</span>
    </div>
    <div class="hx-page">
      <component :is="baseline ? OriginalCreate : CreatePreview" v-model="draft" allowed workflow="studio" :busy="applying" @back="explain">
        <template #sku>
          <div class="sku-section-title"><h2>商品 SKU</h2></div>
          <ElFormItem label="商品 SKU" required>
            <div class="sku-lookup-row"><ElInput v-model="draft.skus[0].code" aria-label="商品 SKU" maxlength="80" placeholder="输入 SKU，获取对应需求" :disabled="applying || importingFiles" @keyup.enter="query" /><ElButton type="primary" plain :loading="querying || applying" :disabled="!draft.skus[0].code.trim() || importingFiles" @click="query">{{ querying ? '正在查询' : applying ? '正在导入' : '获取需求' }}</ElButton></div>
          </ElFormItem>
          <div v-if="notice" class="lookup-notice" aria-live="polite"><ElAlert :title="notice" :type="noticeType" :closable="false" show-icon /><ul v-if="warnings.length"><li v-for="warning in warnings" :key="warning">{{ warning }}</li></ul></div>
          <ElAlert v-if="sourceMismatch" class="lookup-notice" title="当前资料来自其他 SKU，提交前请重新获取需求，或重置表单后手动填写。" type="warning" :closable="false" show-icon />
        </template>
        <template #designer>
          <ElFormItem label="负责设计" required><ElSelect v-model="designer" aria-label="负责设计" placeholder="请选择负责设计" :disabled="applying" style="width:100%"><ElOption v-for="person in designers" :key="person" :value="person" :label="person" /></ElSelect></ElFormItem>
          <ElButton :loading="refreshing" :disabled="applying" @click="refreshDesigners">刷新设计人选</ElButton>
        </template>
        <template #after>
          <OriginalMaterials v-if="baseline" v-model="baselineFiles" :api="baselineApi" editable @failure="explain" />
          <MaterialsPreview v-else :files="files" :disabled="locked" @add="add" @retry="retry" @remove="remove" @download="download" />
          <div class="preview-submit"><ElButton type="primary" :disabled="baseline || !canSubmit" @click="submit">提交图需</ElButton><span v-if="!baseline && files.some(f => f.state === 'failed')" class="submit-hint">请先重试或移除导入失败的附件。</span></div>
        </template>
      </component>
    </div>
    <RequirementPicker v-model="choosing" v-model:selected="selected" :items="matches" :sku="draft.skus[0].code" :busy="applying" @confirm="record => apply(record)" />
    <ElDialog v-model="submitted" title="图需已提交（预览）" width="480px"><ElResult icon="success" title="图需已提交，等待设计审核" sub-title="这是交互演示，没有创建真实任务。"><template #extra><ElButton type="primary" @click="submitted = false">返回表单</ElButton></template></ElResult></ElDialog>
  </OverseasShell>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import OverseasShell from '@/views/overseas/OverseasShell.vue'
import OriginalCreate from '@/views/overseas/OverseasCreate.vue'
import OriginalMaterials from '@/views/overseas/OverseasMaterialsPanel.vue'
import type { Material, MaterialsApi } from '@/api/overseas/materials'
import CreatePreview from './CreatePreview.vue'
import MaterialsPreview from './MaterialsPreview.vue'
import RequirementPicker from './RequirementPicker.vue'
import { designers, scenarios, pause } from './fixtures'
import { useImportPreview } from './use-import-preview'
const { draft, designer, files, querying, applying, choosing, matches, selected, sourceMismatch, notice, noticeType, warnings, locked, canSubmit, reset, query, apply, retry, remove, add, download } = useImportPreview()
const scenario = ref(''), baseline = ref(false), submitted = ref(false), refreshing = ref(false)
const importingFiles = computed(() => files.value.some(f => f.state === 'importing'))
const baselineFiles = ref<Material[]>([])
const baselineApi: MaterialsApi = {
  upload: async () => { throw new Error('原版对照仅展示现有页面，请切回预览体验附件导入。') },
  get: async () => { throw new Error('原版对照没有真实附件。') }, list: async () => [], remove: async () => {},
}
function explain() { ElMessage.info('当前为提交图需的独立交互预览。') }
async function allowReset() {
  if (!files.value.length && !draft.value.name && !designer.value && !draft.value.productName && !draft.value.platform && !draft.value.brand && !draft.value.language) return true
  try { await ElMessageBox.confirm('切换示例或重置会清空当前预览表单，是否继续？', '重置预览', { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' }); return true } catch { return false }
}
async function loadScenario(sku: string) { if (await allowReset()) { reset(sku); baseline.value = false } else scenario.value = '' }
async function clear() { if (await allowReset()) { reset(); scenario.value = ''; baselineFiles.value = [] } }
async function refreshDesigners() { refreshing.value = true; await pause(400); refreshing.value = false; ElMessage.success('设计人选已刷新（预览样例）') }
function submit() { if (canSubmit.value) submitted.value = true }
</script>
