<template>
  <aside class="hx-stack">
    <ElCard class="art-card hx-summary-card" shadow="never"
      ><h2>任务信息</h2>
      <p class="hx-muted">{{ task.id }}</p>
      <p class="hx-footnote">
        品名：{{ task.productName }}<br />品牌：{{ task.brand
        }}<br />提交时间：{{ task.createdAt }}
      </p>
      <p v-for="s in task.skus" :key="s.code" class="hx-footnote">
        {{ s.code }}
      </p>
      <template v-if="'designer' in task">
        <p class="hx-footnote">提交人：{{ task.createdBy.name }}<br />负责设计：{{ task.designer.name }}</p>
        <ElAlert v-if="!task.designer.eligible || task.designer.status !== 'active'" title="当前负责设计已停用或不再具备设计资格，请联系主管改派。" type="warning" :closable="false" />
      </template>
      <p class="hx-footnote">平台：{{ task.platform }}<br />站点 / 语言：{{ task.market }}</p>
      <slot name="assignment" />
      <slot name="materials" /><p class="hx-footnote">{{ task.remarks || "暂无补充说明" }}</p></ElCard
    ><ElCard class="art-card" shadow="never"
      ><template v-if="'requirementsReviews' in task && task.requirementsReviews?.length"><h2>图需审核记录</h2><div v-for="review in task.requirementsReviews" :key="review.id" class="hx-log"><strong>{{ review.decision === 'approve' ? '审核通过' : '退回运营' }}</strong> · {{ review.actorName }} · 提交版本 {{ review.version }}<p>{{ review.comment || '无补充意见' }}</p><small class="hx-muted">{{ review.createdAt }}</small></div></template><h2>流转记录</h2>
      <div v-for="(event, i) in task.events" :key="i" class="hx-log">
        {{ event.title }}<template v-if="'actorName' in event"> · {{ event.actorName }} · 第 {{ event.version }} 版<span v-if="event.beforeDesignerId" class="hx-footnote">{{ event.beforeDesignerId }} → {{ event.afterDesignerId }}</span></template><br /><small class="hx-muted">{{ event.at }}</small>
      </div></ElCard
    >
  </aside>

</template>
<script setup lang="ts">
import type { Task } from "./types";
import type { TaskDetail } from '@/api/overseas/tasks'
defineProps<{ task: Task | TaskDetail }>();
</script>
<style scoped>
h2 {
  font-size: 16px;
}
h3 {
  font-size: 14px;
}
p, .hx-log {
  overflow-wrap: anywhere;
}
</style>
