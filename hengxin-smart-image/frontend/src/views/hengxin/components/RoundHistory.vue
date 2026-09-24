<template>
  <ElCollapse v-model="sections" class="hx-gap">
    <ElCollapseItem :title="`执行与修改记录（${rounds.length}）`" name="history">
      <ElEmpty v-if="!rounds.length" description="暂无轮次记录" :image-size="60" />
      <ElCollapse v-else v-model="expanded" accordion>
        <ElCollapseItem v-for="(round, index) in rounds" :key="round.id" :name="round.id">
          <template #title>
            <div class="round-heading">
              <strong
                >第 {{ index + 1 }} 轮 ·
                {{ round.target === null ? '整套' : `第 ${round.target + 1} 张` }} ·
                {{ round.state }}</strong
              >
              <span
                >{{ formatTime(round.createdAt)
                }}<template v-if="round.baseVersion">
                  · 基于 V{{ round.baseVersion }}</template
                ></span
              >
            </div>
          </template>
          <p class="round-note">
            <strong>用户修改意见</strong><br />{{ round.note || '本轮未填写补充意见' }}
          </p>
          <p class="hx-footnote">操作人：{{ round.operatorId }}</p>
          <ElAlert v-if="round.error" :title="round.error" type="error" :closable="false" />
          <RoundMaterials
            v-if="active && sections.includes('history') && expanded === round.id"
            :key="`${identity}-${taskId}-${round.id}`"
            :task-id="taskId"
            :round-id="round.id"
            :state="round.state"
          />
        </ElCollapseItem>
      </ElCollapse>
    </ElCollapseItem>
  </ElCollapse>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Round } from '@/types/hengxin'
import RoundMaterials from './RoundMaterials.vue'
const props = defineProps<{ taskId: string; rounds: Round[]; active: boolean; identity: string }>()
const sections = ref<string[]>([]),
  expanded = ref('')
function formatTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
watch(
  [() => props.taskId, () => props.identity, () => props.active],
  () => {
    sections.value = []
    expanded.value = ''
  },
  { flush: 'sync' },
)
</script>

<style scoped>
.round-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  padding: 10px 0;
  line-height: 1.6;
  text-align: left;
}
.round-heading span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.round-note {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 8px 0;
}
</style>
