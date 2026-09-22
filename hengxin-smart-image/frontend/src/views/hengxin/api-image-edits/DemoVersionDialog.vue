<template>
  <ElDialog v-model="open" :title="`历史版本 · 原图 ${index + 1}`" width="min(1100px, 96vw)" top="5vh" append-to-body>
    <div v-if="selected && item?.result" class="version-layout">
      <aside class="version-sidebar" aria-label="历史版本列表">
        <div class="version-list-heading"><strong>全部版本</strong><span>{{ versions.length }} 版</span></div>
        <div class="version-list">
          <button v-for="version in versions" :key="version.number" type="button" class="version-option" :class="{ selected: selectedNumber === version.number }" :aria-pressed="selectedNumber === version.number" @click="selectVersion(version.number)">
            <span class="version-option-title"><strong>V{{ version.number }}</strong><ElTag v-if="version.number === currentNumber" size="small">当前</ElTag></span>
            <span>{{ version.created }}</span><span>{{ version.operator || '未记录操作人' }}</span>
          </button>
        </div>
        <p class="version-note">版本按生成时间倒序排列，历史结果始终保留。</p>
      </aside>
      <main class="version-main">
        <ElAlert v-if="versions.length === 1" title="目前只有初始版本。修改成功后，可在这里对比并切换历史结果。" type="info" :closable="false" show-icon />
        <div class="version-comparison">
          <section><h3>选中版本 · V{{ selected.number }} <ElTag v-if="selected.number === currentNumber" size="small">当前</ElTag></h3><div class="version-picture"><PicturePreview :picture="selected.picture" :title="`选中版本 V${selected.number}`" /></div></section>
          <section><h3>当前结果 · V{{ currentNumber }}</h3><div class="version-picture"><PicturePreview :picture="item.result" :title="`当前结果 V${currentNumber}`" /></div></section>
        </div>
        <p class="version-note">点击图片可放大查看。当前结果用于后续修改与整套 ZIP 下载。</p>
        <section class="version-description" aria-label="选中版本详情">
          <div class="version-meta"><span>生成时间：{{ selected.created || '未记录' }}</span><span>操作人：{{ selected.operator || '未记录' }}</span><ElTag size="small" type="info">{{ selected.baseVersion ? `基于 V${selected.baseVersion}` : '初始生成' }}</ElTag></div>
          <h3>修改说明</h3><p class="version-text">{{ selected.text || '初始生成结果，暂无修改说明。' }}</p>
          <div v-if="selected.annotation" class="version-annotation"><strong>标注图</strong><div><PicturePreview :picture="selected.annotation" :title="`V${selected.number} 的修改标注图`" /></div></div>
        </section>
        <ElAlert v-if="restoreReason" :title="restoreReason" type="info" :closable="false" show-icon />
        <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon />
      </main>
    </div>
    <ElEmpty v-else description="暂无成功结果。生成成功后，历史版本会显示在这里。" />
    <template #footer>
      <ElButton @click="open = false">关闭</ElButton>
      <ElButton :disabled="!selected" @click="downloadSelected">下载选中版本</ElButton>
      <ElButton type="primary" :loading="restoring" :disabled="!selected || !!restoreReason || selected.number === currentNumber" @click="restoreSelected">{{ selected?.number === currentNumber ? '已是当前版本' : '设为当前版本' }}</ElButton>
    </template>
  </ElDialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PicturePreview from '../components/PicturePreview.vue'
import { getVersions, restoreVersion, type EditTask } from './preview-state'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: EditTask; index: number; locked?: boolean }>()
const item = computed(() => props.task.items[props.index])
const versions = computed(() => [...getVersions(props.task, props.index)].sort((a, b) => b.number - a.number))
const currentNumber = computed(() => item.value?.result?.version ?? 1)
const selectedNumber = ref<number>()
const selected = computed(() => versions.value.find(version => version.number === selectedNumber.value))
const error = ref(''), restoring = ref(false)
let context = 0
const restoreReason = computed(() => props.locked ? '正在打包下载，完成后可切换当前版本。' : item.value?.revision && item.value.revision.state !== '成功' ? item.value.revision.state === '失败' ? '本次修改失败待重试，重试成功后可切换当前版本；历史版本仍可下载。' : '图片修改处理中，完成后可切换当前版本；历史版本仍可下载。' : '')
watch([open, () => props.task, () => props.index], () => {
  context++
  error.value = ''
  selectedNumber.value = currentNumber.value
}, { immediate: true })
watch(versions, value => {
  if (!value.some(version => version.number === selectedNumber.value)) selectedNumber.value = currentNumber.value
})
function selectVersion(number: number) { selectedNumber.value = number; error.value = '' }
function downloadSelected() {
  if (!selected.value) return
  const { picture, number } = selected.value
  const link = document.createElement('a')
  link.href = picture.url
  link.download = `V${number}-${picture.name}`
  link.click()
}
async function restoreSelected() {
  if (!selected.value || restoring.value || restoreReason.value || selected.value.number === currentNumber.value) return
  const number = selected.value.number, task = props.task, index = props.index, token = context, original = currentNumber.value
  restoring.value = true; error.value = ''
  try {
    try {
      await ElMessageBox.confirm(`将 V${number} 设为当前版本？不会重新生成图片，也不会删除其他历史版本。后续修改和整套 ZIP 下载将使用 V${number}。`, '切换当前版本', { confirmButtonText: '确认设为当前', cancelButtonText: '取消', type: 'warning' })
    } catch { return }
    if (!open.value || token !== context) return
    if (restoreReason.value) { error.value = restoreReason.value; return }
    if (original !== currentNumber.value) { error.value = '当前结果已更新，请重新对比后再切换。'; return }
    restoreVersion(task, index, number)
    ElMessage.success(`已将 V${number} 设为当前版本`)
  } catch (reason) { if (token === context) error.value = reason instanceof Error ? reason.message : '切换失败，请重试' }
  finally { restoring.value = false }
}
</script>

<style scoped>
.version-layout { display:grid; grid-template-columns:190px minmax(0,1fr); gap:24px; max-height:72vh; overflow:auto; color:var(--art-gray-800); }
.version-sidebar, .version-main, .version-comparison section { min-width:0; }
.version-sidebar { border-right:1px solid var(--art-gray-200); padding-right:16px; }
.version-list-heading, .version-option-title { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.version-list-heading { margin-bottom:12px; }
.version-list-heading > span { font-size:12px; color:var(--art-gray-600); }
.version-list { display:flex; flex-direction:column; gap:8px; max-height:52vh; overflow:auto; }
.version-option { display:flex; flex-direction:column; gap:7px; width:100%; padding:12px; text-align:left; background:var(--el-bg-color); border:1px solid var(--art-gray-200); border-radius:8px; color:inherit; cursor:pointer; }
.version-option > span { width:100%; font-size:12px; overflow-wrap:anywhere; }
.version-option strong { font-size:14px; }
.version-option.selected { border-color:var(--el-color-primary); background:var(--el-color-primary-light-9); }
.version-option:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:-2px; }
.version-main { display:flex; flex-direction:column; gap:14px; }
.version-comparison { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
h3 { display:flex; align-items:center; gap:8px; margin:0 0 10px; min-height:24px; font-size:14px; }
.version-picture { height:320px; }
.version-note { margin:0; font-size:12px; line-height:1.7; color:var(--art-gray-600); }
.version-sidebar .version-note { margin-top:12px; }
.version-description { padding:14px; background:var(--art-gray-100); border-radius:8px; }
.version-meta { display:flex; flex-wrap:wrap; gap:8px 16px; margin-bottom:14px; font-size:12px; }
.version-text { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; }
.version-annotation { display:flex; flex-direction:column; gap:8px; margin-top:14px; font-size:13px; }
.version-annotation > div { width:110px; height:100px; }
.version-layout + .el-alert { margin-top:12px; }
@media(max-width:760px) { .version-layout { grid-template-columns:1fr; gap:16px; } .version-sidebar { border-right:0; padding-right:0; } .version-list { flex-direction:row; max-height:none; } .version-option { flex:0 0 150px; } .version-picture { height:230px; } }
@media(max-width:460px) { .version-comparison { grid-template-columns:1fr; } }
</style>
