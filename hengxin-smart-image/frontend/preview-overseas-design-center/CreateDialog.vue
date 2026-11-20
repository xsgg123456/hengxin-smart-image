<template>
  <ElDialog v-model="visible" title="新建图需" class="dc-create-dialog" align-center append-to-body
    :close-on-click-modal="false" @closed="emit('close')">
    <div class="dc-form-content">
      <OverseasCreate v-model="draft" :allowed="true">
        <template #sku>
          <ElFormItem label="商品 SKU" required>
            <ElInput v-model="draft.skus[0].code" maxlength="80" aria-label="商品 SKU"
              placeholder="输入 SKU 自动获取需求，例如 GN-0008" clearable />
            <span v-if="sku" class="dc-lookup-note" role="status">{{ matched ? '已带入商品信息和图需资料' : '未找到该 SKU，可手动填写。' }}</span>
          </ElFormItem>
        </template>
        <template #designer>
          <ElFormItem label="负责设计" required>
            <ElInput model-value="张帅（当前设计）" aria-label="负责设计" readonly />
          </ElFormItem>
        </template>
        <template #after>
          <ElCard class="art-card hx-section" shadow="never">
            <div class="hx-section-title"><h2>图需资料</h2><ElTag type="info" size="small">至少提供一份</ElTag></div>
            <div class="dc-material-grid">
              <section v-for="group in materialGroups" :key="group.kind" class="dc-material-group">
                <h3>{{ group.label }}</h3>
                <ul v-if="materials.some(file => file.kind === group.kind)" class="dc-file-list">
                  <li v-for="file in materials.filter(item => item.kind === group.kind)" :key="file.name">
                    <span>{{ file.name }}</span>
                    <ElButton link type="danger" :aria-label="'移除 ' + file.name" @click="removeFile(file)">移除</ElButton>
                  </li>
                </ul>
                <ElUpload drag multiple action="#" :auto-upload="false" :show-file-list="false"
                  :aria-label="'添加' + group.label" :on-change="item => addFile(item.raw, group.kind)">
                  <strong>点击选择或拖入{{ group.label }}</strong>
                  <small>支持多份 · 单份不超过 500 MB</small>
                </ElUpload>
              </section>
            </div>
          </ElCard>
        </template>
      </OverseasCreate>
    </div>
    <template #footer>
      <div class="dc-form-footer">
        <span v-if="error" class="dc-form-error" role="alert">{{ error }}</span>
        <div><ElButton @click="visible = false">取消</ElButton><ElButton type="primary" @click="submit">提交并进入工作台</ElButton></div>
      </div>
    </template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import OverseasCreate from '@/views/overseas/OverseasCreate.vue'
import { emptyTaskDraft, validateNewDraft } from '@/api/overseas/tasks'
import { sample, type CreateSubmission, type FormMaterial, type MaterialKind } from './form-data'
import { validateFile } from '@/api/overseas/materials'
import './form-dialog.css'

const props = defineProps<{ platform: string }>()
const emit = defineEmits<{ close: []; submit: [payload: CreateSubmission] }>()
const visible = ref(true)
const draft = ref({ ...emptyTaskDraft(), platform: props.platform, designerId: 'preview-current-designer' })
const sku = computed(() => draft.value.skus[0].code.trim().toUpperCase())
const matched = computed(() => sku.value === sample.sku)

const materials = ref<FormMaterial[]>([])
const error = ref('')
const materialGroups = [
  { kind: 'requirement', label: '图片需求文件' },
  { kind: 'competitor', label: '图需参考资料' },
] as const

watch(matched, (found, wasMatched) => {
  error.value = ''
  for (const field of ['name', 'productName', 'brand', 'language'] as const) {
    if (found) draft.value[field] = sample[field]
    else if (wasMatched && draft.value[field] === sample[field]) draft.value[field] = ''
  }
  materials.value = materials.value.filter(file => file.source === 'local')
  if (found) {

    materials.value.push(...sample.materials.filter(file =>
      !materials.value.some(existing => existing.name === file.name && existing.kind === file.kind)))
  }
}, { flush: 'sync' })

function addFile(file: File | undefined, kind: MaterialKind) {
  if (!file) return
  error.value = ''
  try {
    validateFile(file, kind)
    if (materials.value.some(item => item.kind === kind && item.name === file.name)) return
    if (materials.value.length >= 100) throw Error('单次最多 100 份资料')
    materials.value.push({ name: file.name, kind, source: 'local', file })
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法添加此文件'
  }
}
function removeFile(file: FormMaterial) {
  materials.value = materials.value.filter(item => item !== file)
}

function submit() {
  try {
    validateNewDraft(draft.value)
    if (!materials.value.length) throw new Error('请至少添加一份图需资料。')
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '请检查必填信息。'
    return
  }
  const { name, productName, platform, language, brand } = draft.value
  emit('submit', {
    sku: draft.value.skus[0].code.trim(), title: name.trim(), productName: productName.trim(),
    platform, language, brand, designer: '张帅',
    materials: materials.value.map(file => ({ ...file })),
  })
}
</script>

