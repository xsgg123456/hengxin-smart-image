<template>
  <ElCard class="hx-gap execution-progress" shadow="never">
    <template #header>
      <div class="execution-heading"><strong>生图过程</strong>
        <ElSelect v-model="selected" aria-label="查看执行轮次" class="execution-select">
          <ElOption label="当前轮次" :value="CURRENT_EXECUTION_ROUND" />
          <ElOption v-for="(round, index) in history" :key="round.id" :value="round.id"
            :label="`历史轮次 ${index + 1} · ${round.state} · ${formatExecutionTime(round.createdAt)}`" />
        </ElSelect>
      </div>
    </template>
    <ElAlert v-if="isMockMode" title="演示模式：未请求真实执行接口，不提供真实过程记录。" type="info" :closable="false" />
    <template v-else>
      <p v-if="state.loading" role="status">正在加载执行过程…</p>
      <ElAlert v-if="state.error" :title="state.error" type="warning" :closable="false" show-icon>
        <ElButton text type="primary" @click="retry">重试加载过程</ElButton>
      </ElAlert>
      <template v-if="observation">
        <div class="execution-heading" aria-live="polite">
          <strong>{{ executionStageLabel(observation) }}</strong>
          <ElTag v-if="selection.historical" type="info">历史轮次</ElTag>
          <span>耗时：{{ duration === null ? '未提供' : `${Math.floor(duration / 60)}分${duration % 60}秒` }}</span>
        </div>
        <p class="hx-muted">最后活动：{{ formatExecutionTime(observation.lastActivityAt) }}</p>
        <p>检测图片：{{ observation.detectedImages ?? '未知' }} / {{ observation.totalImages }} 张 <ElTag type="info">待校验计数</ElTag></p>
        <p class="hx-footnote">检测数量仅表示发现的图片，不代表校验通过或最终成功数量。</p>
        <ElAlert v-if="stale" title="暂未收到新进展（超过 60 秒），仍在等待更新，不能据此判定失败。" type="warning" :closable="false" />
        <ElAlert v-if="observation.source === 'fixture'" title="这是模拟执行记录，不代表真实模型生成过程。" type="info" :closable="false" />
        <ElAlert v-if="observation.source === 'unavailable'" title="本轮执行器不可用。" type="warning" :closable="false" show-icon />
        <ElAlert v-if="observation.legacy" title="此轮缺少详细历史过程记录；仅展示已保留的执行证据。" type="info" :closable="false" />
        <ElAlert v-if="observation.failure" class="hx-gap" :title="observation.failure.message" type="error" :closable="false" show-icon>
          <p>失败阶段：{{ stages[observation.failure.stage] }}</p>
          <p>建议：{{ observation.failure.action }}</p>
          <ul v-if="observation.failure.slotErrors.length" class="execution-errors">
            <li v-for="(item, index) in observation.failure.slotErrors" :key="`${item.slot}-${index}`">第 {{ item.slot + 1 }} 张：{{ item.message }}</li>
          </ul>
        </ElAlert>
        <section class="hx-gap" aria-label="Codex执行播报">
          <div class="execution-heading"><strong>Codex 执行播报 · {{ presentation.total }} 条</strong>
            <ElButton v-if="presentation.total > 3" text type="primary" :aria-expanded="expanded" @click="expanded = !expanded">
              {{ expanded ? '收起，仅显示最近 3 条' : `展开全部 ${presentation.total} 条` }}
            </ElButton>
          </div>
          <p class="hx-footnote">Codex执行播报，最终结果以平台校验为准</p>
          <p v-if="!presentation.total" class="hx-muted">本轮未采集到 Codex 执行播报。</p>
          <div v-else class="execution-broadcasts" role="region" aria-label="Codex播报记录" tabindex="0">
            <div v-for="event in presentation.broadcasts" :key="event.sequence" class="hx-log">
              <p class="execution-message">{{ event.message }}</p><small>{{ executionEventTime(event) }}</small>
            </div>
          </div>
        </section>
        <ElCollapse v-model="timelineOpen" class="hx-gap">
          <ElCollapseItem title="系统时间线与诊断详情" name="events">
            <p v-if="!presentation.timeline.length" class="hx-muted">暂无系统事件记录</p>
            <div v-for="event in presentation.timeline" :key="event.sequence" class="hx-log">
              <strong>{{ stages[event.stage] }}</strong><span v-if="event.repeats > 1"> · 连续 {{ event.repeats }} 次</span>
              <p v-if="timelineDetail(event)" class="execution-message">{{ timelineDetail(event) }}</p>
              <div><small>{{ executionEventTime(event) }}<template v-if="event.lastAt !== event.at"> — {{ formatExecutionTime(event.lastAt) }}</template></small></div>
            </div>
            <p v-if="observation.failure">错误编号：{{ observation.failure.code }}</p>
            <p v-for="(item, index) in observation.failure?.slotErrors ?? []" :key="index">第 {{ item.slot + 1 }} 张错误编号：{{ item.code }}</p>
          </ElCollapseItem>
        </ElCollapse>
        <div class="execution-heading hx-gap"><span>诊断编号：{{ observation.diagnosticId ?? '未提供' }}</span>
          <ElButton v-if="observation.diagnosticId" size="small" @click="copyDiagnostic">复制诊断编号</ElButton>
        </div>
      </template>
      <p v-else-if="!state.loading && !state.error" class="hx-muted">暂无可查看的执行轮次。</p>
    </template>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { isMockMode } from '@/api/hengxin/client'
import { useUserStore } from '@/store/modules/user'
import { activityIsStale, elapsedSeconds, executionStageLabel, formatExecutionTime, stages } from '@/api/hengxin/execution-data'
import { CURRENT_EXECUTION_ROUND, executionRoundSelection } from '@/api/hengxin/execution-data'
import { useExecutionProgress } from './use-execution-progress'
import { executionEventTime, presentExecutionEvents, timelineDetail, useExecutionDisclosure } from './execution-presentation'

const props = defineProps<{ taskId: string; currentRoundId?: string | null; active: boolean;
  rounds: { id: string; state: string; createdAt: string }[] }>()
const emit = defineEmits<{ detailedFailure: [present: boolean] }>()
const user = useUserStore(), selected = ref(CURRENT_EXECUTION_ROUND)
const identity = computed(() => user.isLogin && user.info.userId != null ? String(user.info.userId) : '')
watch([() => props.taskId, () => props.active, identity], () => { selected.value = CURRENT_EXECUTION_ROUND }, { flush: 'sync' })
const history = computed(() => props.rounds.filter(round => round.id !== props.currentRoundId))
const selection = computed(() => executionRoundSelection(selected.value, props.currentRoundId))
const { state, now, retry } = useExecutionProgress(() => ({ taskId: props.taskId, roundId: selection.value.roundId,
  identity: identity.value, active: props.active, mock: isMockMode }))
const observation = computed(() => state.value.data)
const { expanded, timelineOpen } = useExecutionDisclosure(() => ({ taskId: props.taskId,
  roundId: selection.value.roundId, selected: selected.value, currentRoundId: props.currentRoundId,
  identity: identity.value, active: props.active }))
const presentation = computed(() => presentExecutionEvents(observation.value?.events ?? [], expanded.value))
const duration = computed(() => observation.value ? elapsedSeconds(observation.value, now.value) : null)
const stale = computed(() => observation.value && activityIsStale(observation.value, now.value))
watch(() => !!observation.value?.failure && observation.value.roundId === props.currentRoundId,
  present => emit('detailedFailure', present), { immediate: true, flush: 'sync' })
async function copyDiagnostic() {
  if (!observation.value?.diagnosticId) return
  try { await navigator.clipboard.writeText(observation.value.diagnosticId); ElMessage.success('诊断编号已复制') }
  catch { ElMessage.warning('复制失败，请手动选择诊断编号复制') }
}
</script>
<style scoped>
.execution-progress { min-width: 0; overflow-wrap: anywhere; }
.execution-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; min-width: 0; }
.execution-select { width: 280px; max-width: 100%; }
.execution-errors { margin: 8px 0; padding-left: 20px; }
.execution-broadcasts { max-height: 320px; overflow: auto; }
.execution-message { white-space: pre-wrap; overflow-wrap: anywhere; margin: 4px 0; }
.execution-progress :deep(.el-alert__content) { min-width: 0; }
.execution-progress :deep(.el-collapse-item__header) { height: auto; min-height: 48px; line-height: 1.5; }
</style>
