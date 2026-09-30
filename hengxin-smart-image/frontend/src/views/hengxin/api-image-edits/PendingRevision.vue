<template>
  <section class="pending-revision">
    <ElAlert title="受理结果尚未确认，仅可确认原修改请求。" type="warning" :closable="false" />
    <template v-if="command.kind === 'revise'">
      <p>基于 V{{ command.input.baseVersion }} · {{ operationLabel(command.input.kind) }}</p>
      <RevisionReferences v-if="command.references?.length" :references="command.references" :annotation-url="command.annotation?.url" confirmation />
      <p v-else class="hx-footnote">旧请求未记录完整输入图片清单，无法还原图片数量与顺序。确认时原样重发已保存的请求，不使用当前参考图片或新提示词替换。</p>
      <p v-if="command.input.annotationFileId" class="hx-footnote">原请求标注文件：{{ command.input.annotationFileId }}</p>
      <strong>原修改意见</strong><pre>{{ command.input.text }}</pre>
      <details v-if="command.input.prompt"><summary>原请求保存的提示词</summary><pre>{{ command.input.prompt }}</pre></details>
      <p v-else class="hx-footnote">原请求未保存完整提示词，无法展示；将由服务端确认原请求。</p>
    </template>
    <p v-else>该图片还有待确认的操作，请返回图片卡片确认原操作。</p>
  </section>
</template>
<script setup lang="ts">
import type { ItemCommand } from './item-command'
import { operationLabel } from '@/types/api-image-edits'
import RevisionReferences from './RevisionReferences.vue'
defineProps<{ command: ItemCommand }>()
</script>
<style scoped>
.pending-revision { max-height:65dvh; overflow:auto; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; }
</style>
