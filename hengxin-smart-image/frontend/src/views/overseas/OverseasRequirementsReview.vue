<template>
  <div class="review-columns">
    <div class="review-main">
      <ElCard class="art-card review-panel" shadow="never">
        <div class="review-title"><h2>{{ task.name }}</h2><ElTag>{{ taskStatuses[task.status] }}</ElTag></div>
        <p class="review-meta">图需编号 {{ task.id }} · 当前版本 {{ task.version }}</p>
        <div class="facts">
          <div v-for="item in facts" :key="item[0]"><small>{{ item[0] }}</small><span>{{ item[1] }}</span></div>
        </div>
        <div class="sku-info"><small>商品 SKU</small><ElTag v-for="sku in task.skus" :key="sku.code" type="info">{{ sku.code }}</ElTag></div>
        <div class="remarks"><small>运营补充说明</small><p>{{ task.remarks || '暂无补充说明' }}</p></div>
        <ElAlert v-if="!task.designer.eligible || task.designer.status !== 'active'" title="当前负责设计已停用或失去设计资格，请联系主管改派。" type="warning" :closable="false" />
        <slot name="assignment" />
      </ElCard>
      <OverseasMaterialReader :files="files" :api="materialsApi" @failure="$emit('failure', $event)" />
      <ElCard class="art-card review-panel" shadow="never">
        <h2>审核结论</h2>
        <template v-if="canReview">
          <p class="review-meta">确认需求清楚、资料完整后通过。退回时请说明需要补充的内容。</p>
          <ElForm label-position="top"><ElFormItem label="审核意见（通过可不填，退回必填）"><ElInput v-model="comment" aria-label="图需审核意见" type="textarea" :rows="3" maxlength="2000" :disabled="saving" placeholder="请说明需要补充或调整的内容" /></ElFormItem></ElForm>
          <ElAlert v-if="error" :title="error" type="error" :closable="false" />
          <div class="decision-footer"><small>审核通过前，不启动 AI 分析或生图</small><div><ElButton type="danger" plain :disabled="saving" @click="decide('reject')">退回运营修改</ElButton><ElButton type="primary" :loading="saving" @click="decide('approve')">审核通过，进入 AI 分析</ElButton></div></div>
        </template>
        <p v-else class="review-meta">{{ task.status === 'returned' ? '已退回运营，修改完成后需重新提交设计审核。' : '等待有权处理此任务的设计审核。' }}</p>
        <ElButton v-if="task.capabilities.includes('task.requirements.resubmit')" type="primary" @click="$emit('edit')">修改图需并重新提交</ElButton>
      </ElCard>
      <ElCard class="art-card review-panel" shadow="never"><h2>审核与流转记录</h2>
        <div v-for="review in task.requirementsReviews || []" :key="review.id" class="history"><strong>{{ review.decision === 'approve' ? '审核通过' : '退回运营修改' }}</strong><small>{{ review.actorName }} · {{ formatTaskTime(review.createdAt) }} · 提交版本 {{ review.version }}</small><p>{{ review.comment || '无补充意见' }}</p></div>
        <p v-if="!task.requirementsReviews?.length" class="review-meta">暂无审核记录</p>
        <div v-for="event in task.events" :key="event.id" class="history"><span>{{ event.title }}</span><small>{{ event.actorName }} · {{ formatTaskTime(event.at) }}</small></div>
      </ElCard>
    </div>
    <ElCard class="art-card review-panel review-side" shadow="never"><h2>工作流进度</h2><ElSteps direction="vertical" :active="task.status === 'returned' ? 0 : 1" :space="96" finish-status="success"><ElStep v-for="(stage, i) in STAGES" :key="stage" :title="stage" :description="descriptions[i]" /></ElSteps><p class="side-note">通过 → AI 排版分析<br />退回 → 运营修改并重新提交<br />重新提交 → 回到设计审核</p></ElCard>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { createRequestKeys, taskError, taskStatuses, type TaskDetail, type TasksApi } from '@/api/overseas/tasks'
import type { Material, MaterialsApi } from '@/api/overseas/materials'
import OverseasMaterialReader from './OverseasMaterialReader.vue'
import { STAGES } from './types'
import { formatTaskTime } from './requirements'
const props = defineProps<{ task: TaskDetail; files: Material[]; api: TasksApi; materialsApi: MaterialsApi }>()
const emit = defineEmits<{ changed: [task: TaskDetail]; refresh: []; failure: [reason: unknown]; edit: [] }>()
const comment = ref(''), error = ref(''), saving = ref(false), keys = createRequestKeys()
let active = true
const canReview = computed(() => props.task.status === 'pending_review' && props.task.capabilities.includes('task.requirements.review'))
const facts = computed(() => [['品名', props.task.productName], ['品牌', props.task.brand], ['平台 / 站点', `${props.task.platform} · ${props.task.market}`], ['提交人', props.task.createdBy.name], ['负责设计', props.task.designer.name], ['提交时间', formatTaskTime(props.task.createdAt)]])
const descriptions = ['核对商品信息与图需资料', '核对需求是否清晰、资料是否完整', '仅在设计审核通过后启动', '确认排版和各张图片方案', '按已确认方案执行', '检查结果，按需修改', '全部 SKU 通过后整套归档']
async function decide(decision: 'approve' | 'reject') {
  if (saving.value || !canReview.value) return
  const task = props.task, note = comment.value.trim()
  error.value = ''
  if (decision === 'reject' && !note) { error.value = '请填写退回原因，便于运营修改。'; return }
  saving.value = true
  try {
    await ElMessageBox.confirm(decision === 'approve' ? '通过后将进入 AI 排版分析；后续仍需确认方案才会生图。' : '运营将看到退回原因，修改后需重新提交设计审核。', decision === 'approve' ? '确认通过图需审核？' : '退回运营修改？', { confirmButtonText: '确认', cancelButtonText: '取消', type: decision === 'reject' ? 'warning' : 'info' })
    if (!active || props.task.id !== task.id || props.task.version !== task.version || !canReview.value) return
    const body = { id: task.id, decision, comment: note, version: task.version }
    const result = await props.api.reviewRequirements(task.id, decision, note, task.version, keys.for(body))
    if (!active || props.task.id !== task.id) return
    keys.clear(); comment.value = ''; emit('changed', result)
  } catch (reason) {
    if (!active || props.task.id !== task.id || reason === 'cancel' || reason === 'close') return
    error.value = taskError(reason)
    if (reason instanceof IdentityError && reason.status === 409) emit('refresh')
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally { if (active) saving.value = false }
}
onUnmounted(() => { active = false })
</script>
<style scoped>
.review-columns { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 22px; align-items: start; margin-top: 20px; }
.review-main { display: grid; gap: 20px; min-width: 0; }
.review-panel { border-radius: 16px; }
.review-panel :deep(> .el-card__body) { padding: 24px; }
h2 { font-size: 16px; font-weight: 600; }
.review-title, .decision-footer { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
.review-meta { font-size: 12px; color: var(--el-text-color-secondary); margin: 10px 0 24px; }
.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px 24px; }
small { color: var(--el-text-color-secondary); font-size: 12px; }
.facts small, .remarks small, .history small { display: block; margin-bottom: 7px; }
.sku-info { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--el-border-color-lighter); }
.remarks, .decision-footer { margin-top: 18px; }
.remarks p, .history p { white-space: pre-wrap; line-height: 1.8; }
.review-main, .review-side { overflow-wrap: anywhere; }
.decision-footer > div { display: flex; flex-wrap: wrap; gap: 10px; }
.decision-footer .el-button { margin: 0; }
.review-side { position: sticky; top: 20px; }
.review-side .el-steps { margin-top: 24px; }
.side-note, .history { border-top: 1px solid var(--el-border-color-lighter); padding-top: 18px; margin-top: 18px; line-height: 1.9; }
.side-note { font-size: 12px; color: var(--el-text-color-secondary); }
@media(max-width: 1100px) { .facts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media(max-width: 900px) { .review-columns { grid-template-columns: 1fr; } .review-side { position: static; } }
@media(max-width: 500px) { .facts { grid-template-columns: 1fr; } }
</style>
